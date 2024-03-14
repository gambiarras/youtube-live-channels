import json
import streamlink

from grabber import grabber

channels = grabber.fetch_channels()
json_object = json.dumps(channels, indent=2)

print(json_object)

with open('channels.json', 'w', encoding="utf-8") as outfile:
    outfile.write(json_object)
