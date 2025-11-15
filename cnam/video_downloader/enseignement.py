import re

from bs4 import BeautifulSoup

from cnam.video_downloader.session import requests_session
from cnam.video_downloader.tasks.eu.eu import EuId


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



