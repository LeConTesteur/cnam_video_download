#from moviepy import Compo

from pydantic import BaseModel, RootModel
from pathlib import Path
from typing import List, Dict, Callable, Optional
from moviepy import ImageClip, CompositeVideoClip, VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip, VideoClip, AudioClip
from itertools import islice

Time = float
Position = int
Size = int

VideoUrl = str
Timestamp = int
class Video(BaseModel):
    timestamp: Timestamp
    external_video_url: Optional[VideoUrl]


class ExternalVideo(RootModel):
    root: List[Video]