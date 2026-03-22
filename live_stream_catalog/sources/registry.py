def get_resource_registry() -> list[tuple[str, str]]:
    return [
        ("youtube_channels.json", "youtube"),
        ("twitch_channels.json", "twitch"),
        ("kick_channels.json", "kick"),
    ]