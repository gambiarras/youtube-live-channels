# live-stream-catalog

Builds and maintains a public catalog of live streaming URLs from platforms such as YouTube, Twitch, Kick, and others.

This project is designed to generate a static `channels.json` file that can be publicly accessed via GitHub without requiring paid hosting.

---

## ⚠️ Disclaimer / Legal Notice

This repository **does not host, stream, or distribute any audiovisual content**.

It only:
- collects publicly accessible streaming pages
- resolves their publicly available streaming endpoints (e.g. HLS manifests)
- organizes them into a structured JSON catalog

All content:
- is served directly by the original platforms (YouTube, Twitch, Kick, etc.)
- remains under the responsibility of the respective content owners and platforms

This project:
- does not bypass paywalls, authentication, or DRM
- does not modify or restream any content
- does not guarantee availability, legality, or licensing of any stream

The generated catalog is provided **for informational and convenience purposes only**.

Users are responsible for ensuring compliance with:
- local laws
- platform terms of service
- copyright regulations

---

## How it works

The system operates in two modes:

### `build`
- loads all configured sources
- resolves all channels
- generates a fresh catalog

### `refresh`
- updates only channels with expired or near-expiry URLs
- reduces load and improves availability

---

## Output files

### `channels.json`

Contains resolved streaming URLs and metadata.

### `channels.meta.json`

Contains execution statistics for monitoring.

---

## Project structure

```text
live_stream_catalog/
  models/       # domain models
  io/           # persistence
  sources/      # channel sources
  services/     # build / refresh / resolver
  plugins/      # custom Streamlink plugins