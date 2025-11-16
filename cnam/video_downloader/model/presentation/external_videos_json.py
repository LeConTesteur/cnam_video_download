"""
Modèle de donnée du fichier external_videos.json.
Voici un exemple de contenu :
"""
from typing import List, Optional
from pydantic import BaseModel, RootModel

Time = float
Position = int
Size = int

VideoUrl = str
Timestamp = int
class Video(BaseModel):
    "Noeud Video"
    timestamp: Timestamp
    external_video_url: Optional[VideoUrl]


class ExternalVideo(RootModel):
    "Noeud ExternalVideo"
    root: List[Video]
