import requests
from doit import get_var, create_after
from doit.tools import create_folder
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
from cnam.video_downloader.utils import build_local_file, save_request
from bs4 import BeautifulSoup
import re
import contextvars
from pydantic import TypeAdapter, BaseModel
import json

from datetime import datetime

from urllib.parse import urlparse

base_dir = contextvars.ContextVar("base_dir")

class EuId(BaseModel):
    url: str
    name: str
    
    @property
    def id(self):
        query = urlparse(self.url).query
        m = re.search(r'id=(\d+)', query)
        #print(self.url)
        #print(m)
        #print(m.group(0))
        #print(m.group(1))
        return m.group(1)
    @property
    def netloc(self):
        return urlparse(self.url).netloc

def getCookies(cookie_jar):
    cookie_dict = cookie_jar.get_dict()
    found = ['%s=%s' % (name, value) for (name, value) in cookie_dict.items()]
    return ';'.join(found)

class EuGenericTask(GenericTask, BaseModel):
    eu_id: EuId
    
    @property
    def id(self):
        return self.eu_id.id

    @property
    def folder_eu(self):
        folder = base_dir.get()
        if folder is None:
            raise Exception()
        return Path(folder, self.eu_id.name)

class CreateDirTask(EuGenericTask):



    def to_tasks(self):
        folder_to_create = self.folder_eu
        yield self.new_sub_task(
            name=f'{folder_to_create}',
            actions=[(create_folder, [folder_to_create])]
        )

class CopyPresentationVideoTask(EuGenericTask):
    presentation: Presentation

    @property
    def id(self):
        return f'{self.eu_id.id}_{self.presentation.id}'

    @property
    def target_video_path(self) -> Path:
        date_presentation = datetime.fromtimestamp(self.presentation.metadata.start_time_in_sec)
        return Path(
            self.folder_eu,
            f'presentation_{date_presentation.strftime('%Y%m%d_%H:%M:%S')}.mkv'
        )

    def to_tasks(self):
        target = self.target_video_path
        source = self.presentation.video_path
        yield self.new_sub_task(
            name=str(target),
            actions=[(create_folder, [self.folder_eu]), f'cp {source} {target}'],
            file_dep=[str(source)],
            targets=[str(target)]
        )

class EuTask(EuGenericTask):

    @property
    def main_task_name(self):
        return f'{self.__class__.__name__}_{self.eu_id.id}'

    def build_local_file(self, filename):
        return build_local_file(self.eu_id.id, filename)
    
    def build_presentation_dir(self):
        return self.build_local_file('')

    def connect_moodle(self, session):
        response = session.get(self.eu_id.url)
        #print(response)
        #print(response.text)
        #print(response.url)
        #print(self.eu_id.id)
        soup = BeautifulSoup(response.text, features='html.parser')
        form = soup.select_one('form')
        if form is None:
            return response
        save_request(response, self.eu_id.id)
        url = form.attrs['action']
        relay_state = soup.select_one('input[name=RelayState]')
        saml_response = soup.select_one('input[name=SAMLResponse]')
        if relay_state is None or saml_response is None:
            return response
        
        data = {
            'RelayState':relay_state.attrs['value'],
            'SAMLResponse':saml_response.attrs['value'],
        }
        #print(url)
        #print(data)
        response = session.post(
            url=url,
            data=data
            )
        save_request(response, self.eu_id.id)
        return response

    def get_presentations_from_group(self, session, url, sesskey):
        response = session.get(url)
        #print(response.request.url)
        save_request(response, self.eu_id.id)
        soup = BeautifulSoup(response.text, features='html.parser')
        room = soup.select_one("div[id^=bigbluebuttonbn-recording-table]")
        data_bbb_id=room.attrs['data-bbbid']
        data_tools=room.attrs['data-tools']
        data_group_id=room.attrs['data-group-id']
        data= [{"index":0,"methodname":"mod_bigbluebuttonbn_get_recordings","args":{"bigbluebuttonbnid":data_bbb_id,"tools":data_tools,"groupid":data_group_id}}]
        #print(data)
        response = session.post(f'https://{self.eu_id.netloc}/lib/ajax/service.php?sesskey={sesskey}&info=mod_bigbluebuttonbn_get_recordings',
                                data=json.dumps(data),
                                headers={'content-type': 'application/json',
                                         'Accept': 'application/json, text/javascript, */*; q=0.01',
                                         #'Cookie': getCookies(session.cookies)
                                         })
        #print(response)
        #print(response.request.headers)
        #print(response.request.url)
        save_request(response, self.eu_id.id)
        data = json.loads(response.json()[0]['data']['tabledata']['data'])
        #print(data)
        pres = []
        for play in data:
            soup = BeautifulSoup(play['playback'], features='html.parser')
            recording_id = soup.div.attrs['data-recordingid']
            url=soup.a.attrs['href']
            r = session.get(url, allow_redirects=False)
            print(r)
            print(r.headers)
            redirect_url = r.headers['Location']
            print(redirect_url)
            pres.append(PresentationId(
                recording_id=recording_id, first_url=url, redirect_url=redirect_url))
        return pres

    def get_presentations(self):
        session = requests_session.get()
        #print('------------')
        response = self.connect_moodle(session)
        #print(response.text)
        #print('++++++++++++++')
        #print(response.request.headers)
        #print(session.headers)
        #print(session.cookies.get_dict())
        m=re.search(r'sesskey=([^"]+)',response.text)
        #print(m)
        #print(m.group(1))
        sesskey = m.group(1)

        save_request(response, self.eu_id.id)
        
        soup = BeautifulSoup(response.text, features='html.parser')
        links = soup.select('li.modtype_bigbluebuttonbn a.aalink')
        #print(links)
        pres = []
        for link in links:
            #print(link)
            pres.extend(self.get_presentations_from_group(session, link.attrs['href'], sesskey=sesskey))
        

        #print(pres)
        return pres        
    def to_tasks(self):
        create_dir = CreateDirTask(eu_id=self.eu_id)
        pres_ids = self.get_presentations()
        for pres_id in pres_ids:
            pres = Presentation(presentation_id=pres_id)
            yield from pres.to_tasks()
            yield from CopyPresentationVideoTask(eu_id=self.eu_id, presentation=pres).to_delayed_tasks(
                executed=pres.main_task_name
            )

