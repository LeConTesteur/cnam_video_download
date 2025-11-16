"""
Ensemble des classes et fonctions servant à la création des vidéos de toutes les présentations
de l'EU.
"""
# pylint: disable=abstract-method
from datetime import datetime
from pathlib import Path
import json
import re
from urllib.parse import urlparse

import contextvars

from doit.tools import create_folder
from pydantic import BaseModel

from bs4 import BeautifulSoup


from cnam.video_downloader.tasks.shared.generic_task import GenericTask
from cnam.video_downloader.tasks.presentation.presentation import (
    Presentation,
    PresentationId,
)
from cnam.video_downloader.session import requests_session
from cnam.video_downloader.utils import save_request


base_dir = contextvars.ContextVar("base_dir")

class FolderMissing(Exception):
    """
    Exception levée quand le dossier est manquant
    """

class EuId(BaseModel):
    """
    Identificationo de l'EU
    """
    url: str
    name: str

    @property
    def id(self):
        """
        Donne l'id de l'EU. Se calcule à partir de l'url.
        """
        query = urlparse(self.url).query
        m = re.search(r"id=(\d+)", query)
        return m.group(1)

    @property
    def netloc(self):
        """
        Donne la location réseau de l'EU.
        Chaque CNAM à des urls différentes.
        """
        return urlparse(self.url).netloc


class EuGenericTask(GenericTask, BaseModel):
    """
    Tâche générique liée à l'EU.
    """
    eu_id: EuId

    @property
    def id(self):
        """
        L'id de l'EU.
        """
        return self.eu_id.id

    @property
    def folder_eu(self):
        """
        Le dossier où sera sauvegardé les fichiers de l'EU. 
        """
        folder = base_dir.get()
        if folder is None:
            raise FolderMissing()
        return Path(folder, self.eu_id.name)


class CreateDirTask(EuGenericTask):
    """
    Tâche de création des dossiers de l'EU.
    """
    def to_tasks(self):
        folder_to_create = self.folder_eu
        yield self.new_sub_task(
            name=f"{folder_to_create}", actions=[(create_folder, [folder_to_create])]
        )


class CopyPresentationVideoTask(EuGenericTask):
    """
    Tâche de copie de la vidéo d'une présentation dans le dossier final.
    """
    presentation: Presentation

    @property
    def id(self):
        """
        L'id de la tâche en fonction de l'EU et de la présentation.
        """
        return f"{self.eu_id.id}_{self.presentation.id}"

    @property
    def target_video_path(self) -> Path:
        """
        Le chemin de la vidéo finale.
        """
        date_presentation = datetime.fromtimestamp(
            self.presentation.metadata.start_time_in_sec
        )
        return Path(
            self.folder_eu,
            f"presentation_{date_presentation.strftime('%Y%m%d_%H:%M:%S')}.mkv",
        )

    def to_tasks(self):
        target = self.target_video_path
        source = self.presentation.video_path
        yield self.new_sub_task(
            name=str(target),
            actions=[(create_folder, [self.folder_eu]), f"cp {source} {target}"],
            file_dep=[str(source)],
            targets=[str(target)],
        )


class EuTask(EuGenericTask):
    """
    Tâche principal de l'EU.
    """

    def connect_moodle(self, session):
        """
        S'occupe de l'authentification au moodle.
        """
        response = session.get(self.eu_id.url)
        soup = BeautifulSoup(response.text, features="html.parser")
        form = soup.select_one("form")
        if form is None:
            return response
        save_request(response, self.eu_id.id)
        url = form.attrs["action"]
        relay_state = soup.select_one("input[name=RelayState]")
        saml_response = soup.select_one("input[name=SAMLResponse]")
        if relay_state is None or saml_response is None:
            return response

        data = {
            "RelayState": relay_state.attrs["value"],
            "SAMLResponse": saml_response.attrs["value"],
        }
        response = session.post(url=url, data=data)
        save_request(response, self.eu_id.id)
        return response

    def get_presentations_from_group(self, session, url, sesskey):
        """
        Donne les présentations un groupe de webconférence de l'EU.
        """
        response = session.get(url)
        save_request(response, self.eu_id.id)
        soup = BeautifulSoup(response.text, features="html.parser")
        room = soup.select_one("div[id^=bigbluebuttonbn-recording-table]")
        data = [
            {
                "index": 0,
                "methodname": "mod_bigbluebuttonbn_get_recordings",
                "args": {
                    "bigbluebuttonbnid": room.attrs["data-bbbid"],
                    "tools":  room.attrs["data-tools"],
                    "groupid": room.attrs["data-group-id"],
                },
            }
        ]
        response = session.post(
            f"https://{self.eu_id.netloc}/lib/ajax/service.php"
            f"?sesskey={sesskey}&info=mod_bigbluebuttonbn_get_recordings",
            data=json.dumps(data),
            headers={
                "content-type": "application/json",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
        )

        save_request(response, self.eu_id.id)
        data = json.loads(response.json()[0]["data"]["tabledata"]["data"])
        pres = []
        for play in data:
            soup = BeautifulSoup(play["playback"], features="html.parser")
            recording_id = soup.div.attrs["data-recordingid"]
            url = soup.a.attrs["href"]
            r = session.get(url, allow_redirects=False)
            redirect_url = r.headers["Location"]
            pres.append(
                PresentationId(
                    recording_id=recording_id, first_url=url, redirect_url=redirect_url
                )
            )
        return pres

    def get_presentations(self):
        """
        Donne les présentations pour l'EU.
        """
        session = requests_session.get()
        response = self.connect_moodle(session)
        m = re.search(r'sesskey=([^"]+)', response.text)
        sesskey = m.group(1)

        save_request(response, self.eu_id.id)

        soup = BeautifulSoup(response.text, features="html.parser")
        links = soup.select("li.modtype_bigbluebuttonbn a.aalink")
        pres = []
        for link in links:
            pres.extend(
                self.get_presentations_from_group(
                    session, link.attrs["href"], sesskey=sesskey
                )
            )

        return pres

    def to_tasks(self):
        pres_ids = self.get_presentations()
        for pres_id in pres_ids:
            pres = Presentation(presentation_id=pres_id)
            yield from pres.to_tasks()
            yield from CopyPresentationVideoTask(
                eu_id=self.eu_id, presentation=pres
            ).to_delayed_tasks(executed=pres.main_task_name)
