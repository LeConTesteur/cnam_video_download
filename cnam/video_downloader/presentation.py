import requests
from doit import get_var, create_after
from doit.task import Task, DelayedLoader, dict_to_task
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from cnam.video_downloader.make_video import make_video_task, Slide, DeskShares, DeskShare, ExternalVideo, Metadata
from cnam.video_downloader.shapes_svg_model import Svg
from cnam.video_downloader.desk_shares_xml import Recording as DesksharesRecording
from cnam.video_downloader.metadata_xml import Recording as MetadataRecording

from cnam.video_downloader.external_videos_json import ExternalVideo as ExternalVideoJson
from cnam.video_downloader.tasks import GenericTask
from cnam.video_downloader.session import requests_session
from cnam.video_downloader.utils import build_local_file, youtube_dl_bin

from pydantic import TypeAdapter, BaseModel


class MissingPresentationId(Exception):
    def __init__(self):
        super().__init__('Presentation id is missing')



def build_task_prepare_presentation(presentation_id):
    yield build_task_create_dir(presentation_id)
    yield from build_task_download_base_files(presentation_id)

def task_prepare_presentation(presentation_id):
    if presentation_id is None:
        raise MissingPresentationId()
    yield from build_task_prepare_presentation(presentation_id)

def get_base_files_from_presentation(presentation_id):
    return {
        build_local_file(presentation_id, "captions.json"): "captions.json",
        build_local_file(presentation_id, "deskshare.xml"): "deskshare.xml",
        build_local_file(presentation_id, "external_videos.json"): "external_videos.json",
        build_local_file(presentation_id, "metadata.xml"): "metadata.xml",
        build_local_file(presentation_id, "panzooms.xml"): "panzooms.xml",
        build_local_file(presentation_id, "presentation_text.json"): "presentation_text.json",
        build_local_file(presentation_id, "shapes.svg"): "shapes.svg",
        build_local_file(presentation_id, "cursor.xml"): "cursor.xml",
        build_local_file(presentation_id, "slides_new.xml"): "slides_new.xml",
        build_local_file(presentation_id, "tldraw.json"): "tldraw.json",
        build_local_file(presentation_id, "webcams.mp4"): "video/webcams.mp4",
        build_local_file(presentation_id, "webcams.webm"): "video/webcams.webm",
        build_local_file(presentation_id, "deskshare.mp4"): "deskshare/deskshare.mp4",
        build_local_file(presentation_id, "deskshare.webm"): "deskshare/deskshare.webm",
    }

def build_url(path):
    return f"https://bbb6.lecnam.net/{path}"

def build_presentation_url(presentation_id, path):
    return f"presentation/{presentation_id}/{path}"

def is_file_exist(filename):
    return Path(filename).is_file()

def download_file(path, targets):
    #import sys
    #print(build_url(path), file=sys.stderr)
    session = requests_session.get()
    req = session.get(
        path
    )
    #print(req.status_code, file=sys.stderr)
    if req.status_code == 200:
        with open(targets[0], mode='wb') as fd:
            fd.write(req.content)

class PresentationId(BaseModel):
    recording_id:str
    first_url: str
    redirect_url: str
    
    @property
    def id(self):
        return Path(self.redirect_url).name

class BasePresentationTask(GenericTask, BaseModel):
    presentation_id: PresentationId

    
    @property
    def id(self):
        return self.presentation_id.id
    
    def save_id(self):
        with open(self.build_local_file('presentation_id.json'), 'w', encoding='utf-8') as fd:
            fd.write(self.presentation_id.json())

    def build_local_file(self, filename):
        return build_local_file(self.presentation_id.id, filename)
    
    def build_presentation_dir(self):
        return self.build_local_file('')
    
    def build_url(self, path):
        url = urlparse(self.presentation_id.redirect_url)
        #print(url)
        #print(url._replace(path=path).geturl())
        return url._replace(path=path).geturl()

    def build_presentation_url(self, path):
        return self.build_url(f"presentation/{self.presentation_id.id}/{path}")


    @property
    def video_path(self):
        return self.build_local_file('video.mkv')
    
    @property
    def metadata(self) -> Metadata:
        try:
            with open(self.build_local_file('metadata.xml'), mode='r', encoding='utf-8') as fd:
                data = fd.read()
                mydoc: MetadataRecording = MetadataRecording.from_xml(data)
                return Metadata(
                    duration_in_ms = mydoc.playback.duration,
                    start_time_in_ms = mydoc.start_time
                )
        except FileNotFoundError:
            return None
    
    @property
    def shapes(self) -> Svg:
        try:
            with open(self.build_local_file('shapes.svg'), mode='r', encoding='utf-8') as fd:
                return Svg.from_xml(fd.read())
        except FileNotFoundError:
            return None
    @property
    def deskshare(self) -> DesksharesRecording:
        try:
            with open(self.build_local_file('deskshare.xml'), mode='r', encoding='utf-8') as fd:
                    return DesksharesRecording.from_xml(fd.read())
        except FileNotFoundError:
            return None
class CreateDirTask(BasePresentationTask):
    
    def to_tasks(self):
        DIRS = [self.build_presentation_dir(), self.build_local_file("slides"), self.build_local_file("videos")]
        def is_dir_exist():
            return all([Path(d).is_dir() for d in DIRS])
        yield Task(
            name= self.build_presentation_dir(),
            uptodate= [is_dir_exist],
            actions= [f"mkdir -p {' '.join(DIRS)}"],
            subtask_of=self.main_task.name
        )


class DownloadBaseFilesTask(BasePresentationTask):
    def to_tasks(self):
        yield self.main_task
        for filename, url in get_base_files_from_presentation(self.presentation_id.id).items():
            task = Task(
                name=filename,
                targets=[filename],
                uptodate=[is_file_exist(filename)],
                actions=[
                    (download_file, [self.build_presentation_url(url)])
                ],
                subtask_of=self.main_task.name
            )
            self.main_task.task_dep.append(task.name)
            yield task

class DownloadSlides(BasePresentationTask):
    def to_tasks(self):
        def gen_tasks(fd):
            mydoc: Svg = Svg.from_xml(fd.read())
            for image in mydoc.root:
                filename = image.a_id
                target_svg = self.build_local_file(f'slides/{filename}{image.suffix}')
                target_png = self.build_local_file(f'slides/{filename}.png')

                url = image.a_href
                task = Task(
                    name= target_svg,
                    actions= [(download_file, [self.build_presentation_url(url)])],
                    uptodate= [is_file_exist(target_svg)],
                    targets= [target_svg],
                    subtask_of=self.main_task.name
                )
                self.main_task.task_dep.append(task.name)
                yield task
                if image.suffix != '.png':
                    task = Task(
                        name= f'{target_svg} to png',
                        actions= [f'rsvg-convert -w {image.a_width} -h {image.a_height} -o {target_png} {target_svg}'],
                        file_dep= [target_svg],
                        targets= [target_png],
                        subtask_of=self.main_task.name
                    )
                    self.main_task.task_dep.append(task.name)
                    yield task
        try:
            with open(self.build_local_file('shapes.svg'), mode='r', encoding='utf-8') as fd:
                yield from gen_tasks(fd)
        except FileNotFoundError:
            pass

class DownloadExternalVideos(BasePresentationTask):

    def to_tasks(self):
        def gen_tasks(fd):
            youtube_dl = youtube_dl_bin.get()
            external_videos = TypeAdapter(ExternalVideoJson).validate_json(fd.read())
            for index, external_video in enumerate(external_videos.root):
                target = self.build_local_file(f'video/external_video_{index}.mkv')
                if external_video.external_video_url is None:
                    continue
                yield {
                    'name': target,
                    'actions': [f'{youtube_dl} -o {target} {external_video.external_video_url} || true'],
                    'targets': [target],
                }
        try:
            with open(self.build_local_file('external_videos.json'), mode='r', encoding='utf-8') as fd:
                yield from gen_tasks(fd)
        except FileNotFoundError:
            pass

class MakeVideoTask(BasePresentationTask):
    def to_tasks(self):
        slides = []
        desk_shares = None
        mydoc = self.shapes
        if mydoc:
            slides = [
                Slide(
                    path=Path(self.build_local_file(f'slides/{image.a_id}.png')),
                    start=image.a_in,
                    end=image.a_out,
                    x=image.a_x,
                    y=image.a_y,
                    width=image.a_width,
                    height=image.a_height
                )
                for image in mydoc.root
            ]
        mydoc = self.deskshare
        if mydoc:
            desk_shares = DeskShares(
                path=self.build_local_file('deskshare.webm'),
                desk_shares=[
                    DeskShare(
                        start=event.start_timestamp,
                        end=event.stop_timestamp,
                        width=event.video_width,
                        height=event.video_height)
                    for event in mydoc.root
                ]
            )
        yield from make_video_task(
            output=self.build_local_file('video.mkv'),
            slides=slides,
            metadata=self.metadata,
            audio_file=self.build_local_file('webcams.webm'),
            desk_shares=desk_shares
        )

class Presentation(BasePresentationTask):

    def to_tasks(self):
        yield self.main_task
        create_dir = CreateDirTask(presentation_id=self.presentation_id)
        download_base_file = DownloadBaseFilesTask(presentation_id=self.presentation_id)
        download_slides = DownloadSlides(presentation_id=self.presentation_id)
        download_external_videos = DownloadExternalVideos(presentation_id=self.presentation_id)
        make_video = MakeVideoTask(presentation_id=self.presentation_id)
        yield from create_dir.to_tasks()
        yield from download_base_file.to_tasks()
        yield from download_slides.to_delayed_tasks(
            executed=download_base_file.main_task.name,
            target_regex=download_slides.build_local_file('slides/*')
        )
        yield from download_external_videos.to_delayed_tasks(
            executed=download_base_file.main_task.name,
            target_regex=download_slides.build_local_file('video/*')
        )
        yield from make_video.to_delayed_tasks(
            executed=download_slides.main_task.name
        )

@create_after(executed='prepare_presentation', )
def task_presentation(presentation_id):
    def gen():
        yield from build_task_presentation(presentation_id)
    if presentation_id is None:
        raise MissingPresentationId()
    return DelayedLoader(
        gen,
        executed='',
        target_regex=build_local_file(get_var('presentation', None),'slides/*')
    )
        
        

@create_after(executed='presentation', target_regex=build_local_file(get_var('presentation', None), 'video/*'))
def task_video_presentation(presentation_id):
    presentation_id = get_var('presentation', None)
    if presentation_id is not None:
        yield from build_task_make_video(presentation_id)



def build_task_presentation(presentation_id):
    #yield from build_task_download_slides(presentation_id)
    yield from build_task_external_videos(presentation_id)







#@create_after(executed='download_base_files', target_regex=build_local_file('slides/*'))


#@create_after(executed='download_base_files', target_regex=build_local_file('slides/*'))
def build_task_external_videos(presentation_id):
    def gen_tasks(fd):
        external_videos = TypeAdapter(ExternalVideoJson).validate_json(fd.read())
        for index, external_video in enumerate(external_videos.root):
            target = build_local_file(presentation_id,f'video/external_video_{index}.mp4')

            yield {
                'name': target,
                'actions': f'{YOUTUBE_DL_BIN} -t mp4 -o {target} {external_video.external_video_url}',
                'targets': [target],
            }
    try:
        with open(build_local_file(presentation_id,'external_videos.json'), mode='r', encoding='utf-8') as fd:
            yield from gen_tasks(fd)
    except FileNotFoundError:
        pass



#@create_after(executed='download_slides', target_regex=build_local_file('video/*'))
def build_task_make_video(presentation_id):
    slides = []
    desk_shares = None
    try:
        with open(build_local_file(presentation_id,'shapes.svg'), mode='r', encoding='utf-8') as fd:
            mydoc: Svg = Svg.from_xml(fd.read())
            slides = [
                Slide(
                    path=Path(build_local_file(presentation_id,f'slides/{image.a_id}.png')),
                    start=image.a_in,
                    end=image.a_out,
                    x=image.a_x,
                    y=image.a_y,
                    width=image.a_width,
                    height=image.a_height
                )
                for image in mydoc.root
            ]
    except FileNotFoundError:
        pass
    try:
        with open(build_local_file(presentation_id,'deskshare.xml'), mode='r', encoding='utf-8') as fd:
            mydoc: Recording = Recording.from_xml(fd.read())
            desk_shares = DeskShares(
                path=build_local_file(presentation_id,'deskshare.webm'),
                desk_shares=[
                    DeskShare(
                        start=event.start_timestamp,
                        end=event.stop_timestamp,
                        width=event.video_width,
                        height=event.video_height)
                    for event in mydoc.root
                ]
            )
    except FileNotFoundError:
        pass
    yield from make_video_task(
        build_local_file(presentation_id,'video.mp4'), slides, build_local_file(presentation_id,'webcams.webm'), desk_shares=desk_shares)