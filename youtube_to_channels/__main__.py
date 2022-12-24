import json

from grabber import youtube_grabber, dailymotion_grabber

youtube_channels = youtube_grabber.fetch_channels()
dailymotion_channels = dailymotion_grabber.fetch_channels()

json_object = json.dumps(youtube_channels + dailymotion_channels, indent=2)

with open('channels.json', 'w', encoding="utf-8") as outfile:
    outfile.write(json_object)
