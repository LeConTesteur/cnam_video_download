import requests
from doit import get_var, create_after
from doit.task import Task, DelayedLoader, dict_to_task
from pathlib import Path
import xml.etree.ElementTree as ET
from cnam.video_downloader.make_video import make_video_task, Slide, DeskShares, DeskShare, ExternalVideo
from cnam.video_downloader.shapes_svg_model import Svg
from cnam.video_downloader.desk_shares_xml import Recording
from cnam.video_downloader.external_videos_json import ExternalVideo as ExternalVideoJson
from cnam.video_downloader.tasks import GenericTask
from cnam.video_downloader.presentation import Presentation, PresentationId
from cnam.video_downloader.session import requests_session
from cnam.video_downloader.utils import build_local_file
from cnam.video_downloader.eu import EuId
from bs4 import BeautifulSoup
import re

from pydantic import TypeAdapter, BaseModel
import json



class Enseignement:

    def get_eu(self):
        session = requests_session.get()
        #print('------------')
        response = session.get('https://lecnam.net/enseignements')
        #print(response)
        #print(response.text)
        #print(response.url)
        soup = BeautifulSoup(response.text, features='html.parser')
        cards = soup.select('a.card.description-card.one-card')

        ret= []
        for card in cards:
            href = card['href']
            #print(card)
            p_title = card.select_one('div.card-block p.text:nth-child(1) p.text')
            #p_title = soup('a.card.description-card.one-card  p.text')
            #print(p_title)
            #print(p_title.text)
            match = re.match(r'^(\w+)', p_title.text)
            eu_name = match.group(1)
            #print(eu_name)
            if not eu_name:
                raise Exception()
            ret.append(EuId(url=href, name=eu_name))
        #print(ret)
        return ret



