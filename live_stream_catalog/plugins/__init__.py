from streamlink import Streamlink

from live_stream_catalog.plugins.kick import register_kick_plugin

def register_custom_plugins(session: Streamlink) -> None:
    register_kick_plugin(session)