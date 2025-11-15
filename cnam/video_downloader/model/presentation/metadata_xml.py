from typing import List, Optional
from pydantic_xml import BaseXmlModel, RootXmlModel, attr, element
from pydantic import computed_field
from pathlib import Path

"""
<?xml version="1.0"?>
<recording>
  <id>834c9292041b9047ebe2061075cf2984b80e6a2d-1741369843904</id>
  <state>published</state>
  <published>true</published>
  <start_time>1741369843904</start_time>
  <end_time>1741375480408</end_time>
  <participants>20</participants>
  <meeting id="834c9292041b9047ebe2061075cf2984b80e6a2d-1741369843904" externalId="ff2ba3c3d83ff31b2eebfe666bbff12a51141341-10225-18174[0]" name="Regroupement n&#xB0;1 - vendredi 07 mars 2025 19h 20h30" breakout="false"/>
  <breakout/>
  <breakoutRooms/>
  <meta>
    <isBreakout>false</isBreakout>
    <meetingId>ff2ba3c3d83ff31b2eebfe666bbff12a51141341-10225-18174[0]</meetingId>
    <bbb-recording-description>Pr&#xE9;sentation de l&#x2019;UE et du formateur et des attendues</bbb-recording-description>
    <bbb-context-name>SEC101 - FOD IDF : Cybers&#xE9;curit&#xE9; : r&#xE9;f&#xE9;rentiel, objectifs et d&#xE9;ploiement (2024 - 2025 Semestre 2)</bbb-context-name>
    <bbb-origin-server-common-name/>
    <bbb-recording-name>Regroupement n&#xB0;1 - vendredi 07 mars 2025 19h 20h30</bbb-recording-name>
    <bbb-recording-tags/>
    <bbb-origin-server-name>idf.moodle.lecnam.net</bbb-origin-server-name>
    <bbb-origin-tag>moodle-mod_bigbluebuttonbn (2023100900)</bbb-origin-tag>
    <bbb-context-id>10225</bbb-context-id>
    <bbb-origin>Moodle</bbb-origin>
    <meetingName>Regroupement n&#xB0;1 - vendredi 07 mars 2025 19h 20h30</meetingName>
    <bbb-context>SEC101 - FOD IDF : Cybers&#xE9;curit&#xE9; : r&#xE9;f&#xE9;rentiel, objectifs et d&#xE9;ploiement (2024 - 2025 Semestre 2)</bbb-context>
    <bbb-origin-version>4.3.10 (Build: 20250210)</bbb-origin-version>
    <bbb-meeting-size-hint>33</bbb-meeting-size-hint>
    <bbb-context-label>SEC101_FOD IDF_2024 - 2025_Semestre 2_144610</bbb-context-label>
  </meta>
  <playback>
    <format>presentation</format>
    <link>https://bbb3.lecnam.net/playback/presentation/2.3/834c9292041b9047ebe2061075cf2984b80e6a2d-1741369843904</link>
    <processing_time>652354</processing_time>
    <duration>4684838</duration>
    <extensions>
      <preview>
        <images/>
      </preview>
    </extensions>
    <size>59181388</size>
  </playback>
  <raw_size>95830302</raw_size>
</recording>
"""

NSMAP = {'':"http://www.w3.org/2000/svg",'xlink':"http://www.w3.org/1999/xlink"}

class Meta(BaseXmlModel, tag='meta', search_mode='unordered'):
    bbb_context: str = element(tag='bbb-context')


class PlaybackExtensions(BaseXmlModel, tag='extensions'):
    pass
class Playback(BaseXmlModel, tag='playback'):
    format: str = element(tag='format')
    link: str = element(tag='link')
    processing_time: int = element(tag='processing_time')
    duration: int = element(tag='duration')
    extensions: Optional[PlaybackExtensions] = element(tag='extensions', default=None)
    size: int = element(tag='size')

class Recording(BaseXmlModel, tag='recording', search_mode='unordered'):
    #a_id: str = attr(name='id')
    #a_style: str = attr(name='style')
    #a_version: str = attr(name='version')
    #a_viewBox: str = attr(name='viewBox')
    id: str = element(tag='id')
    state: str = element(tag='state')
    published: bool = element(tag='published')
    start_time: int = element(tag='start_time')
    end_time: int = element(tag='end_time')
    participants: int = element(tag='participants')
    meeting: Optional[str] = element(tag='meeting', default=None)
    breakout: Optional[str] = element(tag='breakout', default=None)
    breakoutRooms: Optional[str] = element(tag='breakoutRooms', default=None)
    meta: Meta = element(tag='meta')
    playback: Playback = element(tag='playback')
    raw_size: int = element(tag='raw_size')