from typing import Union

from .types import Track

import aiofiles
import asyncio
import math
import json
import re
import os

DEFAULT_FONT_SIZE = 18
SUBTITLES_STYLE = "Style: WAmpeg,Trebuchet MS,%s,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,1,2,10,10,10,1\n"
SUBTITLES_CREDITS = "Dialogue: 0,0:00:00.00,0:00:10.00,WAmpeg,,0,0,0,,{\\an8}Seguiteci su Telegram: @WickedAnime\n"

DIALOGUE_PATTERN = r"Dialogue:\s*[^,]+,[^,]+,[^,]+,([^,]+)"
STYLE_PATTERN = r"Style:\s*([^,]+),[^,]+,([^,]+)"

async def get_mediainfo(file, format="json", slow=True):
    args = ["mediainfo"]
    if slow:
        args.append("--ParseSpeed=1.0")
    if format == "json":
        args.append("--Output=JSON")
    proc = await asyncio.create_subprocess_exec(
        *args, file,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode()
    if stderr:
        raise Exception(stderr.decode())
    if format == "json":
        json_format = json.loads(output)
        return json_format["media"]["track"][1:]
    return output

async def get_ffprobe(file):
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", file, "-hide_banner", "-show_streams",
        "-print_format", "json", "-loglevel", "fatal",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode()
    if stderr:
        raise Exception(stderr.decode())
    return json.loads(output).get("streams", [])

async def extract_subtitles(input, output, offset, credits: bool=True):
    async def fix_subtitles():
        async with aiofiles.open(output, "r", encoding="utf-8") as f:
            data = await f.read()
            r = re.sub(';.+', '', data)
        
        async with aiofiles.open(output, "w+", encoding="utf-8") as f:
            await f.write(r)

    track_offset = f"0:{offset}"
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", input,
        "-map", track_offset, output,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if not os.path.exists(output):
        raise Exception("Estrazione %s fallita.\n %s" % (stdout.decode(), stderr.decode()))
    if credits:
        await add_subtitles_credits(output)
    await fix_subtitles()
    return output

async def extract_fonts(input, directory):
    fonts = os.listdir(directory)
    streams = [stream for stream in await get_ffprobe(input)
        if stream.get("codec_type") == "attachment"]
    mapping = [
        f'{index}:{directory}/{stream["tags"]["filename"]}'
        for index, stream in enumerate(streams, 1)
        if stream["tags"]["filename"] not in fonts
    ]
    proc = await asyncio.create_subprocess_exec(
        "mkvextract", input, "attachments", *mapping,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

async def add_subtitles_credits(subtitles: str):
    async with aiofiles.open(subtitles, "r", encoding="utf-8") as f:
        lines = await f.readlines()
    file_content = "\n".join(lines)
    font_size = get_font_size(file_content)
    for i, line in enumerate(lines):
        if "\0" in line:
            lines[i] = line.replace("\0", "")
        if line == "[V4+ Styles]\n":
            lines.insert(i+2, SUBTITLES_STYLE % font_size)
        if line == "[Events]\n":
            lines.insert(i+2, SUBTITLES_CREDITS)
    # Sovrascriviamo il contenuto del file
    async with aiofiles.open(subtitles, "w+", encoding="utf-8") as f:
        await f.writelines(lines)
    return subtitles

def get_track_by_key_value(
    tracks: list[dict],
    key: str,
    value: Union[str, re.Pattern],
    filter: str=None,
):
    for idx, track in enumerate(tracks):
        if key not in track:
            continue
        if filter and track.get("@type") != filter:
            continue
        if isinstance(value, re.Pattern):
            if match := value.search(track[key]):
                return idx
        elif isinstance(value, str):
            if track[key] == value:
                return idx
    raise Exception("Nessuna traccia trovata con i parametri inseriti.")


def get_font_size(content: str):
    if playres := re.search(r"PlayResY:\s*(\d+)", content):
        height = int(playres[1])
        return math.ceil(height * (DEFAULT_FONT_SIZE / 288))
    else:
        # Nessuna PlayRes, utilizziamo la grandezza
        # dello stile più usato.
        dialogues = re.findall(DIALOGUE_PATTERN, content)
        most_used = max(dialogues, key=dialogues.count)
        styles = re.findall(STYLE_PATTERN, content)
        for style, font_size in styles:
            if style != most_used:
                continue
            return font_size