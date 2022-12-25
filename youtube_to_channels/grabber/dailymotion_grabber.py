import requests
import json

from importlib import resources
from models.channel import Channel

__session = requests.Session()

def __grab(id):
    try:
        response = __session.get(f'https://www.dailymotion.com/player/metadata/video/{id}').json()['qualities']['auto'][0]['url']
        m3u = __session.get(response).text
        m3u = m3u.strip().split('\n')[1:]
        d = {}
        cnd = True

        for item in m3u:
            if cnd:
                resolution = item.strip().split(',')[2].split('=')[1]
                if resolution not in d:
                    d[resolution] = []
            else:
                d[resolution]= item
            cnd = not cnd

        m3u = d[max(d, key=int)]
    except Exception as e:
        m3u = None

    return m3u


def channel_from(data):
    stream = __grab(data['channel_id'])

    return Channel(
        data['id'],
        data['name'],
        stream,
        data['logo'],
        data.get('group', 'web')
    )

def fetch_channels():
    with resources.open_text("resources", "dailymotion_channels.json") as file:
        data = json.load(file)

        channels = list(map(channel_from, data))

        channels = [channel for channel in channels if channel.url is not None]
        return list(map(lambda channel: channel._asdict(), channels))
