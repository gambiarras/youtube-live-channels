import json
import re
import requests

from importlib import resources
from models.channel import Channel

__session = requests.Session()

def __grab(url):
    response = __session.get(url, timeout=15).text
    return next(iter(re.findall(r"(?<=hlsManifestUrl\":\").*\.m3u8", response)), None)

def channel_from(data):
    stream = __grab(data['url'])

    return Channel(
        data['id'],
        data['name'],
        stream,
        data['logo'],
        data.get('group', 'web')
    )

def fetch_channels():
    with resources.open_text("resources", "youtube_channels.json") as file:
        data = json.load(file)

        channels = list(map(channel_from, data))

        channels = [channel for channel in channels if channel.url is not None]
        return list(map(lambda channel: channel._asdict(), channels))
