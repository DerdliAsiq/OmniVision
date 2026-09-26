# OmniVision: Tactical C2 Surveillance Platform

## Website

https://omnivision-q8xdmnay.manus.space/

## Overview

OmniVision is an open-source, edge-oriented surveillance and command-and-control (C2) platform for fixed facilities and field operations. It combines real-time object detection and tracking (YOLO + ByteTrack), a tactical HUD, an async SQLite evidence pipeline, and a FastAPI web terminal for remote monitoring and control.

Maintainer: DerdliAsiq. License: MIT (see `LICENSE`).

Current version: `2.0` (single source: `config.py: SystemState.VERSION`). Canonical model: `yolo26x` (single source: `config.py: SystemState.MODEL_NAME`).

## Features

- **Detection and tracking:** YOLO inference with configurable stride (`PROCESS_INTERVAL`), ByteTrack IDs, trace history, per-class target filtering with persistent selection ("iron memory").
- **C2 web terminal:** FastAPI + MJPEG (`/video_feed`), log search (`/api/logs` with `q/limit/offset`), summary, CSV export, media/source control, target selection, playback and volume commands. HTTP Basic Auth on all endpoints.
- **Evidence pipeline:** Async SQLite (`tactical_vision_v2.db` at `config.SystemState.DB_PATH`) in WAL mode, bounded queue, ALARM snapshots under `evidence_captures/`, 1-day retention with hourly purge.
- **HUD and telemetry:** OpenCV overlay with FPS, source label, playback state, CPU/RAM diagnostics, LiDAR readout, polygon zones, strobe highlight for locked targets.
- **Voice C2 (optional):** Offline faster-whisper (`whisper_model_local/`) with `alfa` wake word. Disabled by default; toggle at runtime.
- **LiDAR/sonar input:** Serial readout with simulation fallback when no port is present. Displayed only when enabled.
- **Source manager:** Camera, local video loop (`Video_Analiz/`), RTSP, generic HTTP streams, YouTube VOD (download + loop + seek) and YouTube LIVE (direct, no seek).

Horizon/skyline ROI for USV pitch/roll compensation is on the roadmap and not implemented.

## Hardware matrix

| Component | Field (Raspberry Pi 5) | HQ (reference) |
| :-------- | :--------------------- | :------------- |
| CPU | Cortex-A76 | AMD Ryzen 5 7535HS (3.3–4.4 GHz) |
| GPU | XNNPACK / Arm NEON (CPU) | NVIDIA RTX 2050 4 GB (CUDA, FP16) |
| RAM / Disk | 8 GB LPDDR4X | 16 GB DDR5 / 512 GB NVMe |
| YOLO model | `yolo26n` Nano / INT8 (planned) | `yolo26x` (canonical) |
| Expected | ~15–25 FPS | Depends on GPU, resolution, and stride |

## Quickstart

```shell
# OS deps (Arch/Garuda example)
sudo pacman -S tk mpg123

git clone https://github.com/DerdliAsiq/OmniVision.git
cd OmniVision

python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# HQ / CUDA
pip install -r requirements.txt

# Field / Pi 5 / CPU-only (instead of the above)
# pip install -r requirements-pi.txt

# Pre-fetch model weights (also auto-fetched on first detector init)
python download_model.py

# Run (starts OpenCV loop + web server)
python main.py
```

Headless (no OpenCV window, web only):

```shell
HEADLESS=1 python main.py
```

Diagnostics:

```shell
python test_project.py
python test_mic.py   # microphone check for Voice C2
```

## Web terminal

Default: `http://127.0.0.1:8000`. LAN bind requires explicit opt-in (see Configuration).

- `GET /` — dashboard (Operations + Intelligence Archive tabs)
- `GET /video_feed` — MJPEG stream
- `GET /api/logs?q=&limit=100&offset=0` — threat logs (dict rows, paginated)
- `GET /api/summary` — 24h distinct-object counts
- `GET /api/export_csv` — CSV report
- `GET /api/media` — local videos + playback state
- `GET /api/classes` — model class map
- `POST /api/command` — `toggle_alarm`, `toggle_hud`, `toggle_track`, `set_targets`, `set_source`, `play_pause`, `seek_fwd/back`, `vol_up/down/mute/max`
- `DELETE /api/wipe` — clears logs (VACUUM) and `ALARM_*` evidence images only

## Keyboard shortcuts

| Key | Action |
| :-- | :----- |
| `S` | Target selection menu |
| `C` | Source menu (camera / Video_Analiz / RTSP / YouTube) |
| `Space` | Pause / resume |
| `,` / `.` | −5s / +5s (seekable sources only) |
| `A` | Alarm mode on/off |
| `D` | HUD show/hide |
| `T` | Tracking overlay on/off |
| `V` | Voice C2 on/off |
| `H` | Debug overlay on/off |
| `Z` | Polygon zone on/off |
| `L` | LiDAR display on/off |
| `P` | Performance panel on/off |
| `Q` | Clean shutdown |

Source behavior:

- `Video_Analiz/*.mp4|avi|mov|mkv` — infinite loop with PTS pacing.
- RTSP (`rtsp://...`) — low-latency TCP, no seek.
- YouTube VOD — downloaded to `Video_Analiz/_yt_<id>.mp4`, then loop + seek. Requires `yt-dlp` + Node.js LTS (`winget install OpenJS.NodeJS.LTS` on Windows).
- YouTube LIVE — direct stream, no seek, 30 fps cap.
- ALARM snapshots go to `evidence_captures/` and are served at `/evidence_captures/<file>`.

Tk menus run on a single dedicated service thread and are non-blocking. To disable Tk entirely and use web only: `OMNIVISION_TK=0`.

## Voice commands

Enable with `[V]`, then prefix every command with the `alfa` wake word (example: `alfa alarm aktif`). Without the prefix the utterance is ignored.

| Utterance | Effect |
| :-------- | :----- |
| `alfa alarm aktif` | Alarm on |
| `alfa alarm kapat` | Alarm off |
| `alfa panel aç` | Show HUD |
| `alfa panel gizle` / `alfa panel kapat` | Hide HUD |

Requires `PyAudio`. If the engine reports not ready, check `pip install PyAudio` and `python test_mic.py`. Model files live in `whisper_model_local/` (not committed; fetched on first run).

## Configuration

Copy `.env.example` to `.env`:

| Variable | Default | Notes |
| :------- | :------ | :---- |
| `C2_USERNAME` / `C2_PASSWORD` | `admin` / `1234` | Change in production. With defaults the server binds `127.0.0.1` only. |
| `C2_ALLOW_LAN` | `0` | Set `1` to bind `0.0.0.0` (trusted LAN/VPN only, no HTTPS). |
| `C2_PORT` | `8000` | Web port. |
| `LIDAR_PORT` / `LIDAR_BAUD` | `auto` / `115200` | Force e.g. `COM4` or `/dev/ttyUSB0`. |
| `PROCESS_INTERVAL` | `3` | Inference stride (1 = every frame). |
| `OMNIVISION_TK` | `1` | `0` disables Tk menus. |
| `HEADLESS` | `0` | `1` disables the OpenCV window. |

Security notes: Basic Auth without TLS, no rate limiting — do not expose to the internet. Use LAN/VPN. `DELETE /api/wipe` is destructive (confirmation in UI + auth required).

## Dependencies

- `ultralytics` — YOLO core (`config.py: SystemState.MODEL_NAME`)
- `supervision` — annotators + ByteTrack
- `fastapi` + `uvicorn` — C2 server
- `opencv-python` — capture, HUD, MJPEG encoding
- `torch` — CUDA (`requirements.txt`) or CPU (`requirements-pi.txt`)
- `faster-whisper`, `SpeechRecognition`, `PyAudio` — Voice C2
- `pyserial`, `psutil`, `pygame`, `python-dotenv`, `yt-dlp`

## Repository hygiene

Not committed (see `.gitignore`): `*.pt`, `*.db*`, `whisper_model_local/`, `Video_Analiz` media, `evidence_captures` images, `venv/`. Tracked placeholders: `Video_Analiz/README.txt`, `evidence_captures/.gitkeep`.

## License

MIT. See `LICENSE`.
