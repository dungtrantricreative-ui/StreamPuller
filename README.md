# StreamPuller

Torrent Movie Downloader. Enter a movie name → auto-search → download → normalize to MP4 1080p.

Single-file. No dependencies besides libtorrent, requests, ffmpeg.

## Install

```bash
sudo apt-get install -y ffmpeg
pip install libtorrent requests
```

## CLI Usage

```bash
python main.py "Interstellar" -q 1080p -p review
python main.py "magnet:?xt=urn:btih:..." -q 720p
```

## Google Colab

```python
import subprocess, sys
subprocess.run(["apt-get", "install", "-y", "ffmpeg"], capture_output=True)
subprocess.run(["pip", "install", "libtorrent", "requests"], capture_output=True)
subprocess.run(["git", "clone", "https://github.com/dungtrantricreative-ui/StreamPuller.git"], capture_output=True)
sys.path.insert(0, '/content/StreamPuller')

from main import download_movie
result = download_movie("Interstellar", "/content/PhimTai", "1080p", "review")
```

## Profiles

| Profile | CRF | Codec | Quality |
|---------|-----|-------|---------|
| review | 18 | H.264 | Best (largest) |
| standard | 20 | H.264 | Balanced |
| compressed | 23 | H.264 | Smaller |
| h265 | 22 | H.265 | Most compressed |

MIT License
