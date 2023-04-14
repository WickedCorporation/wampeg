from enum import Enum

class Codec(Enum):
    H264 = "libx264"
    AAC = "aac"
    COPY = "copy"