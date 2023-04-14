import aiofiles

from hashlib import md5
from random import randint

from .utils import *
from .types import Settings, Track
from .enums import Codec

class WAmpeg:
    SUBTITLES_TEMPLATE = open("template.ass").read()
    IMAGE_BASED_SUBTITLES = ["VobSub", "PGS"]
    MAX_VIDEO_SIZE = 4000000000
    DESIRED_VIDEO_SIZE = 3900000000

    ENCODING_ARGS = [
        "-pix_fmt", "yuv420p", "-tune", "animation",
        # "-vsync", "0", "-partitions", "partb8x8+partp4x4+partp8x8+parti8x8",
        # "-b-pyramid", "1", "-weightb", "1", "-8x8dct", "1", "-fast-pskip", "1",
        # "-direct-pred", "1", "-coder", "ac", "-trellis", "1", "-me_method", "hex",
        # "-flags", "+loop", "-sc_threshold", "40", "-keyint_min", "24", "-g", "48",
        # "-qmin", "3", "-qmax", "51"
    ]

    def __init__(
        self,
        input: str,
        output: str,
        video: dict,
        audio: dict,
        subtitles: dict=None
    ):
        self.input = input
        self.output = output
        self.settings = Settings()

        self.video_track = Track(video)
        self.audio_track = Track(audio)

        self.subtitles = Track(subtitles) if subtitles else None
    
    async def setup(self):
        self.settings.video_map = f"0:{self.video_track.offset}"
        self.settings.audio_map = f"0:{self.audio_track.offset}"

        # Rencode video in H264 se il codec è diverso o sono presenti sottotitoli
        if self.video_track.format != "AVC" or self.video_track.profile == "High 10" or self.subtitles:
            self.settings.video_codec = Codec.H264
            self.settings.video_bitrate = self.video_track.bitrate

        # Rencode audio in AAC se il codec è diverso
        if self.audio_track.format != "AAC" or self.audio_track.channels >= 6.0:
            self.settings.audio_codec = Codec.AAC

        # Rencode video in H264 se la traccia video supera il limite
        if self.video_track.size > self.MAX_VIDEO_SIZE:
            self.settings.video_codec = Codec.H264
            self.settings.video_bitrate = self.calculate_bitrate()

        return await self.make_command()
        
    async def make_command(self):
        self.settings.command.extend([
            "ffmpeg", "-y", "-i", self.input,
            "-max_muxing_queue_size", "9999",
            "-map_chapters", "-1",
            "-movflags", "faststart",
            "-bsf:a", "aac_adtstoasc"
        ])
        # Se sono presenti sottotitoli, estrarre e aggiungere al comando
        if self.subtitles:
            self.settings.subtitles_file = (
                f"{md5(self.input.encode()).hexdigest()}{randint(100, 500)}.ass"
            )
            if self.subtitles.format not in self.IMAGE_BASED_SUBTITLES:
                await extract_subtitles(self.input, self.settings.subtitles_file, self.subtitles.offset)
                self.settings.command.extend(["-vf", f"subtitles={self.settings.subtitles_file}:fontsdir=fonts"])
            else:
                # Creiamo un file di sottotitoli per i crediti dal template
                async with aiofiles.open(self.settings.subtitles_file, "w+", encoding="utf-8") as f:
                    await f.write(self.SUBTITLES_TEMPLATE.format(
                        SUBTITLES_STYLE % DEFAULT_FONT_SIZE, SUBTITLES_CREDITS))
                self.settings.video_map = "[finalvideo]"
                self.settings.command.extend([
                    "-filter_complex", f"[0:{self.subtitles.offset}]" \
                        f"scale=width={self.video_track.width}:height={self.video_track.height}," \
                        f"crop=w={self.video_track.width}:h={self.video_track.height}[subtitles];" \
                        f"[0:{self.video_track.offset}][subtitles]overlay[video];" \
                        f"[video]subtitles={self.settings.subtitles_file}:fontsdir=fonts[finalvideo]",
                ])
        self.settings.command.extend(["-map", self.settings.video_map, "-map", self.settings.audio_map])
        # Se il bitrate è impostato, aggiungere al comando
        if self.settings.video_bitrate:
            bitrate = str(self.settings.video_bitrate)
            self.settings.command.extend([
                "-b:v", bitrate, "-maxrate", bitrate,
                "-minrate", bitrate, "-bufsize", bitrate
            ])
        # Se il codec audio non è COPY, aggiungere parametri al comando
        if self.settings.audio_codec != Codec.COPY:
            self.settings.command.extend(["-ac", "2.0"])
        # Se il codec video non è COPY, aggiungere parametri al comando
        if self.settings.video_codec != Codec.COPY:
            self.settings.command.extend(self.ENCODING_ARGS)

        self.settings.command.extend([
            "-c:v", self.settings.video_codec.value,
            "-c:a", self.settings.audio_codec.value,
            self.output
        ])
        return self.settings.command
            
    def calculate_bitrate(self):
        return (self.DESIRED_VIDEO_SIZE * self.video_track.bitrate) // self.video_track.size
