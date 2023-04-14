from dataclasses import dataclass, field
from .enums import Codec

import re

@dataclass
class Settings:
    command: list = field(default_factory=list)
    video_bitrate: int = field(default=None)
    video_map: str = field(default=None)
    audio_map: str = field(default=None)
    subtitles_map: str = field(default=None)
    subtitles_file: str = field(default=None)
    video_codec: Codec = field(default=Codec.COPY)
    audio_codec: Codec = field(default=Codec.COPY)

class Track:
    MAPPING = {"Yes": True, "No": False}
    CHANNELS_RE = re.compile(r"(\d+)(?:[\s\d\/]+)?")
    def __init__(self, data: dict):
        self.type: str = data.get("@type")
        self.title: str = data.get("Title")

        # TS has idx-idx
        streamOrder: str = data.get("StreamOrder", "0")
        self.offset: int = int(streamOrder.split('-')[-1])

        self.format: str = data.get("Format")
        self.profile: str = data.get("Format_Profile")
        self.channels: float = float(
            self.CHANNELS_RE.match(
                data.get("Channels", "1")).group(1)
        )
        self.duration: float = float(data.get("Duration", 0))
        self.size: float = float(data.get("StreamSize", 0))
        self.bitrate: int = int(data.get("BitRate", 0))
        self.width: int = int(data.get("Width", 0))
        self.height: int = int(data.get("Height", 0))
        self.framerate: float = float(data.get("FrameRate", 0))
        self.colorspace: str = data.get("ColorSpace")
        self.chroma: str = data.get("ChromaSubsampling")
        self.encoding: str = data.get("Encoded_Library_Name")
        self.language: str = data.get("Language")
        self.default: bool = self.MAPPING.get(data.get("Default"))
        self.forced: bool = self.MAPPING.get(data.get("Forced"))