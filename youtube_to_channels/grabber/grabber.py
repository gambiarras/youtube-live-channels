import json
import streamlink

from importlib import resources
from models.channel import Channel

def __grab(url, resolution):
    try:
        streams = streamlink.streams(url)
        stream = streams.get(resolution)
        return None if stream is None else stream.url
    except:
        pass
    
    return None

def channel_from(data):
    resolution = "best" if data.get('resolution') is None else data.get('resolution')
    stream = __grab(data['url'], resolution)

    return Channel(
        data['id'],
        data['name'],
        stream,
        data['logo'],
        data.get('group', 'web')
    )

def fetch_channels_from(resourse):
    with resources.open_text("resources", resourse) as file:
        data = json.load(file)

        channels = list(map(channel_from, data))

        channels = [channel for channel in channels if channel.url is not None]
        return list(map(lambda channel: channel._asdict(), channels))

def fetch_channels():
    resources = [
        "youtube_channels.json",
        "twitch_channels.json"
    ]

    channels = []
    for resource in resources:
        channels.extend(fetch_channels_from(resource))

    return channels
