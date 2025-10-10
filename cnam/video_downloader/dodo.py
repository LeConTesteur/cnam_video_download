import requests
from doit import get_var, create_after
from doit.doit_cmd import DoitMain
from doit.cmd_base import TaskLoader2
from pathlib import Path
from itertools import chain
import xml.etree.ElementTree as ET
from cnam.video_downloader.make_video import make_video_task, Slide, DeskShares, DeskShare, ExternalVideo
from cnam.video_downloader.shapes_svg_model import Svg
from cnam.video_downloader.desk_shares_xml import Recording
from cnam.video_downloader.external_videos_json import ExternalVideo as ExternalVideoJson
from cnam.video_downloader.presentation import Presentation, PresentationId
from cnam.video_downloader.eu import EuTask, EuId, base_dir
from cnam.video_downloader.tasks import GenericTask
from cnam.video_downloader.enseignement import Enseignement
from cnam.video_downloader.session import authentification
from cnam.video_downloader.utils import youtube_dl_bin
from pydantic import TypeAdapter, BaseModel
import click


class Credential(BaseModel):
    username: str
    password: str

class MyLoader(TaskLoader2):
    def __init__(self, output_dir, eu_id_items: list[tuple[int, str]], presentation_urls, credential: Credential, verbosity):
        self.eu_id_items = eu_id_items
        self.presentation_urls = presentation_urls
        self.credential = credential
        self.verbosity = verbosity
        base_dir.set(output_dir)
        youtube_dl_bin.set('yt-dlp')

    def setup(self, opt_values):
        authentification(self.credential.username, self.credential.password)

    def load_doit_config(self):
        return {'verbosity': self.verbosity}

    def load_tasks(self, cmd, pos_args):
        print('loads')
        
        list_to_tasks = []
        for eu_id_item in self.eu_id_items:
            list_to_tasks.append(EuTask(eu_id=eu_id_item[0], name=eu_id_item[1]))
        
        for presentation_url in self.presentation_urls:
            list_to_tasks.append(Presentation(presentation_id=PresentationId(recording_id='',first_url='', redirect_url=presentation_url)))

        if not list_to_tasks:
            for eu_id in Enseignement().get_eu():
                list_to_tasks.append(EuTask(eu_id=eu_id))

        return list(chain(
            *(element.to_tasks() for element in list_to_tasks)
            ))
        
        
@click.command()
@click.option('--output-dir',required=True , type=click.Path(file_okay=False, dir_okay=True, writable=True, exists=True))
@click.option('eu_id_items', '--eu-id', nargs=2, multiple=True, type=(int, str))
@click.option('--presentation-url', multiple=True, type=str)
@click.option('--username', envvar='CNAM_USERNAME', prompt=True, hide_input=True, required=True)
@click.option('--password', envvar='CNAM_PASSWORD', prompt=True, required=True)
@click.option('--verbosity', type=click.IntRange(0, 2), default=0)
def main(output_dir, eu_id_items, presentation_url, username, password, verbosity):
    import sys
    sys.exit(
        DoitMain(
            MyLoader(
                output_dir,
                eu_id_items,
                presentation_url,
                credential=Credential(username=username, password=password),
                verbosity=verbosity
            )
        ).run([])
    )

if __name__ =='__main__':
    main()