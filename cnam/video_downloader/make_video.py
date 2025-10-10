#from moviepy import Compo

from pydantic import BaseModel
from pathlib import Path
from typing import List, Dict, Callable, Optional
from moviepy import ImageClip, CompositeVideoClip, VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip, VideoClip, AudioClip
from itertools import islice
from datetime import timedelta

Time = float
Position = int
Size = int


class Dimension(BaseModel):
    width: Size
    height: Size

class Slide(BaseModel):
    path :Path
    start: Time
    end: Time
    x: Position
    y: Position
    width: Size
    height: Size

Slides = List[Slide]


class Video(Slide):
    pass


class DeskShare(BaseModel):
    start: Time
    end: Time
    width: Size
    height: Size


class DeskShares(BaseModel):
    path: Path
    desk_shares: List[DeskShare]

GetVideoClip = Callable[[],VideoClip]
GetAudioClip = Callable[[],AudioClip]

class Metadata(BaseModel):
    duration_in_ms: int
    start_time_in_ms: int
    
    @property
    def start_time_in_sec(self) -> int:
        return self.start_time_in_ms//1000

class ExternalVideo(BaseModel):
    start: Time
    path: Path


class VideosToCompose(BaseModel):
    _videos: Dict[Time, GetVideoClip] = {}
    _audio: GetAudioClip = None
    
    def add_get_clip(self, start: Time, get_clip: GetVideoClip):
        if start is None:
            raise ValueError('Start must be time type')
        self._videos[start]=get_clip
    
    def add_audio(self, get_clip: GetAudioClip):
        self._audio = get_clip
    
    @property
    def clips(self) -> List[GetVideoClip]:
        return list(map(lambda x: x[1], sorted(self._videos.items(), key=lambda x: x[0])))
    
    @property
    def videos(self) -> List[VideoClip]:
        return list(clip() for clip in self.clips)
    
    @property
    def audio(self) -> GetAudioClip:
        return self._audio

class ConvertElement(BaseModel):
    source: Path
    target: Path
    action: Dict

class ConvertVideo(ConvertElement):
    get_clip: GetVideoClip
    start: Time

class ConvertAudio(ConvertElement):
    get_clip: GetAudioClip

class ConvertToCompose(BaseModel):
    _videos: List[ConvertVideo] = []
    _audio:  ConvertAudio = None

    @property
    def videos(self) -> List[ConvertVideo]:
        return sorted(self._videos, key=lambda x: x.start)
    
    @property
    def audio(self) -> ConvertAudio:
        return self._audio

    def add_video(self, video: ConvertVideo):
        if video.start is None:
            raise ValueError('Start must be time type')
        self._videos.append(video)
    
    def add_audio(self, audio: ConvertAudio):
        self._audio = audio

FPS=1
#def to_composite(videos_to_compose: VideosToCompose, targets):
#    #img_clips = []
#    #for slide in slides:
#    #    source = str(slide.path.with_suffix('.mp4'))
#    #    img_clips.append(VideoFileClip(source))
#        #source = slide
#        #img = ImageClip(source.path).with_start(source.start).with_duration(source.end).with_position(("center", "center"))
#        #img_clips.append(img)
#    #comp = CompositeVideoClip(img_clips)
#    comp = concatenate_videoclips(videos_to_compose.videos)
#    if videos_to_compose.audio:
#        comp.audio = CompositeAudioClip([videos_to_compose.audio()])
#    else:
#        comp.without_audio()
#    comp.write_videofile(targets[0], fps=FPS)

def get_path_of_videos(videos_convert: ConvertToCompose):
    return [
        video.target for video in videos_convert.videos
    ]

def ffmpeg_to_composite(videos_convert: ConvertToCompose, duration_in_ms, targets):
    def build_list_concat_file(targets):
        with open(targets[0], 'w', encoding='utf-8') as fd:
            count_parent = len(Path(targets[0]).parents)
            remove_parent = Path(*['..']*(count_parent-1))
            for path in get_path_of_videos(videos_convert):
                print(f"file '{Path(remove_parent, path)}'", file=fd)
    file_concat = Path(targets[0] +'_concat.txt')
    video_without_audio = Path(targets[0]+'_video_without_audio.mp4')
    video = targets[0]
    print(get_path_of_videos(videos_convert))
    yield {
        'name': file_concat,
        'actions': [(build_list_concat_file,[])],
        'file_dep': get_path_of_videos(videos_convert),
        'targets': [file_concat]
        
    }
    yield {
        'name': video_without_audio,
        'actions': [f'ffmpeg -y -f concat -safe 0 -i {file_concat} -c copy -video_track_timescale 600 -t {duration_in_ms}ms {video_without_audio}'],
        'file_dep': [file_concat],
        'targets': [video_without_audio]
    }
    yield {
        'name': video,
        'actions': [f'ffmpeg -y -i {video_without_audio} -i {videos_convert.audio.target} -c copy  {video}'],
        'file_dep': [video_without_audio, videos_convert.audio.target],
        'targets': [video]
    }

def to_image_clip(source: Slide, width, height):
    target = str(source.path.with_suffix('.mp4'))
    #print(source)
    end = source.end if source.end > 1 else 1
    img = ImageClip(source.path).with_start(source.start).with_duration(end).with_position(("center", "center"))
    return ConvertVideo(
        source=source.path,
        target=target,
        get_clip=lambda: img,
        action={
        'name': target,
        'actions': [f'ffmpeg -y -loop 1 -i {source.path} -c:v libx264 -t \'{source.end - source.start}s\' -pix_fmt yuv420p -vf scale={width}:{height} {target}'],
        'file_dep': [source.path],
        'targets': [target]},
        start= source.start
    )

def write_video(video: VideoClip, targets):
    video.write_videofile(targets[0], fps=FPS)


def convert_video(source: Slide, width, height):
    convert = to_image_clip(source=source, width=width, height=height)
    return convert
    #print(convert)
    #return ConvertVideo(
    #    source=convert.source,
    #    target=convert.target,
    #    get_clip=lambda: VideoFileClip(convert.target),
    #    action={
    #        'name': convert.target,
    #        'actions': [(write_video,[convert.get_clip()])],
    #        'file_dep': [convert.source],
    #        'targets': [convert.target],
    #    },
    #    start= convert.start
    #)

def convert_audio(audio_file) -> ConvertVideo:
    audio_file = Path(audio_file)
    target = audio_file.with_suffix('.convert.opus')
    return ConvertAudio(
        source=audio_file,
        target=target,
        get_clip=lambda: AudioFileClip(target),
        action={
            'name': target,
            'actions': [f'ffmpeg -y -i "{audio_file}" -ac 2 -c:a libopus -b:a 96K {target}'],
            'file_dep': [audio_file],
            'targets': [target],
        }
    )
    
def desk_shares_to_video(path: Path, desk_share: DeskShare, dimension: Dimension, targets):
    video = VideoFileClip(path).subclipped(desk_share.start, desk_share.end)
    video.resized(width=dimension.width,height=dimension.height)
    write_video(video, targets)

def convert_desk_shares(desk_shares: DeskShares, dimension: Dimension) -> List[ConvertVideo]:
    def build_convert(index: int, path: Path, desk_share: DeskShare):
        print('+++++++++++++++++')
        print(list(path.parents))
        print(path.parent)
        print(path.stem)
        target = Path(path.parent, f'{path.stem}_{index}.mp4')
        return ConvertVideo(
            source=path,
            target=target,
            get_clip=lambda : VideoFileClip(target),
            action={
                'name': target,
                'actions': [f'ffmpeg -y -ss \'{desk_share.start}s\' -t \'{desk_share.end-desk_share.start}s\' -i \'{path}\' -acodec copy -vcodec copy \'{target}\''],
                'file_dep': [path],
                'targets': [target],
            },
            start=desk_share.start
        )
    return [
        build_convert(index, desk_shares.path, desk_share)
        for index, desk_share in enumerate(desk_shares.desk_shares)
    ]

def convert_external_videos(external_videos: List[ExternalVideo]) -> List[ConvertVideo]:
    def build_convert(index: int, external_video: ExternalVideo):
        return ConvertVideo(
            source=external_video.path,
            target=external_video.path,
            get_clip=lambda : VideoFileClip(external_video.path),
            action={},
            start=external_video.start
        )
    return [
        build_convert(index, external_video)
        for index, external_video in enumerate(external_videos)
    ]

def get_size(slide: Slide) -> Dimension:
    return Dimension(width=slide.width, height=slide.height)

def make_video_task(output: Path, slides: Slides, metadata: Metadata, audio_file: Path = None, desk_shares: DeskShares = None, external_videos: List[ExternalVideo] = None):
    converts = []
    videos_to_compose = ConvertToCompose()
    if audio_file:
        convert = convert_audio(audio_file)
        videos_to_compose.add_audio(convert)
        converts.append(convert)
    for slide in slides:
        #converts.append(to_image_clip(slide))
        converts.append(convert_video(slide, width=960, height=540))
    file_dep = []
    if desk_shares:
        converts.extend(convert_desk_shares(desk_shares, get_size(slides[0])))
    if external_videos:
        converts.extend(convert_external_videos(external_videos=external_videos))
    for convert in converts:
        if hasattr(convert, 'start'):
            videos_to_compose.add_video(convert)
        file_dep.append(convert.target)
        if convert.action:
            yield convert.action
    #yield {
    #    'name': output,
    #    'actions': [(ffmpeg_to_composite,[videos_to_compose])],
    #    'file_dep': file_dep,
    #    'targets': [output],
    #}
    yield from ffmpeg_to_composite(videos_to_compose, metadata.duration_in_ms, [output])