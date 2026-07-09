
#!/usr/bin/env python3
"""
StreamPuller v2.1 - Torrent Movie Downloader

Auto-search torrent by movie name (YTS + 1337x fallback)
→ download via libtorrent → normalize to MP4.

Usage:
    python main.py "Movie Title" [--quality 1080p] [--profile review]
    python main.py "magnet:?xt=urn:btih:..." [--quality 720p]
    python main.py --hot-movies # New: Discover hot movies
"""
import argparse
import logging
import os
import subprocess
import sys
import time
import requests
import json # Thêm import json để xử lý dữ liệu API
import warnings

# Tắt các cảnh báo không cần thiết từ libtorrent
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Cấu hình logging chi tiết hơn
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

# ── YTS Search ───────────────────────────────────────────────────────

YTS_DOMAINS = ["yts.lt", "yts.ag", "yts.mx", "yts.bz"]
YTS_TIMEOUT = 5  # seconds per domain (fast fail)


def _yts_get(query: str, quality: str = "all", limit: int = 10) -> list:
    """Search YTS API with fast timeout."""
    log.info(f"Searching YTS for '{query}' with quality '{quality}'...")
    params = {
        "query_term": query,
        "sort_by": "seeds",
        "order_by": "desc",
        "limit": limit,
    }
    for domain in YTS_DOMAINS:
        url = f"https://{domain}/api/v2/list_movies.json"
        try:
            log.debug(f"Attempting YTS API call to {url}")
            r = requests.get(url, params=params, timeout=YTS_TIMEOUT)
            r.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = r.json()
            if data.get("status") == "ok" and data.get("data", {}).get("movie_count", 0) > 0:
                log.info(f"Successfully fetched results from {domain}")
                return _parse_yts_movies(data.get("data", {}), quality)
            else:
                log.warning(f"YTS API from {domain} returned no movies or status not 'ok'. Status: {data.get('status')}")
        except requests.exceptions.RequestException as e:
            log.warning(f"Could not fetch from YTS domain {domain}: {e}")
        except json.JSONDecodeError as e:
            log.error(f"Failed to decode JSON from YTS domain {domain}: {e}")
    log.info("No results from YTS after trying all domains.")
    return []


def _parse_yts_movies(data: dict, quality: str) -> list:
    """Parse YTS API response into structured movie list."""
    movies = []
    for m in data.get("movies", []):
        torrents = []
        for t in m.get("torrents", []):
            q = t["quality"]
            if quality == "all" or q == quality:
                torrents.append({
                    "quality": q,
                    "size": t["size"],
                    "size_bytes": t["size_bytes"],
                    "seeds": t["seeds"],
                    "peers": t["peers"],
                    "hash": t["hash"],
                    "magnet": (
                        f"magnet:?xt=urn:btih:{t['hash']}"
                        f"&dn={m['title_long'].replace(' ', '+')}"
                        f"&tr=udp://tracker.opentrackr.org:1337/announce"
                        f"&tr=udp://open.tracker.cl:1337/announce"
                        f"&tr=udp://tracker.torrent.eu.org:451/announce"
                        f"&tr=udp://tracker.dler.org:6969/announce"
                        f"&tr=udp://bt2.archive.org:6969/announce"
                    ),
                })
        if torrents:
            torrents.sort(key=lambda x: x["seeds"], reverse=True)
            movies.append({
                "title": m["title"],
                "year": m["year"],
                "rating": m.get("rating", 0),
                "genres": m.get("genres", []),
                "runtime": m.get("runtime", 0),
                "torrents": torrents,
                "best_torrent": torrents[0],
            })
    return movies


# ── 1337x Search (fallback) ──────────────────────────────────────────

def _1337x_search(query: str, quality: str = "all", limit: int = 10) -> list:
    """Search 1337x as fallback when YTS fails."""
    log.info(f"Searching 1337x for '{query}' with quality '{quality}'...")
    try:
        url = f"https://1337x.to/search/{query}/1/"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=8)
        r.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        if r.status_code != 200:
            log.warning(f"1337x returned status code {r.status_code}")
            return []

        import re
        rows = re.findall(
            r'<td class="name"><a href="/torrent/(\d+)/([^"]+)">([^<]+)</a></td>'
            r'.*?<td>([\d.]+)</td>.*?<td>(\d+)</td>.*?<td>(\d+)</td>',
            r.text, re.DOTALL | re.IGNORECASE
        )

        results = []
        for tid, slug, name, size_str, seeds, leechs in rows[:limit]:
            # Try to extract year
            import re as re2
            year_match = re2.search(r'\b(19|20)\d{2}\b', name)
            year = int(year_match.group()) if year_match else 0

            # Try to extract quality
            q_match = re2.search(r'(1080p|720p|4k|2160p|480p)', name, re.IGNORECASE)
            q = q_match.group(1) if q_match else "720p"

            # Size parsing
            size_bytes = _parse_size(size_str)

            magnet = f"magnet:?xt=urn:btih:{slug.replace('-', '')[:40]}"
            results.append({
                "title": name,
                "year": year,
                "rating": 0,
                "genres": [],
                "runtime": 0,
                "torrents": [{
                    "quality": q,
                    "size": size_str,
                    "size_bytes": size_bytes,
                    "seeds": int(seeds),
                    "peers": int(leechs),
                    "hash": slug[:40],
                    "magnet": f"magnet:?xt=urn:btih:{slug.replace('-', '')[:40]}"
                              f"&dn={name.replace(' ', '+')}"
                              f"&tr=udp://tracker.opentrackr.org:1337/announce"
                              f"&tr=udp://open.tracker.cl:1337/announce"
                              f"&tr=udp://tracker.torrent.eu.org:451/announce"
                              f"&tr=udp://tracker.dler.org:6969/announce",
                }],
                "best_torrent": None,
            })

        for r_item in results:
            if r_item["torrents"]:
                r_item["best_torrent"] = r_item["torrents"][0]

        log.info(f"Found {len(results)} results from 1337x.")
        return results
    except requests.exceptions.RequestException as e:
        log.error(f"Error fetching from 1337x: {e}")
    except Exception as e:
        log.error(f"An unexpected error occurred during 1337x search: {e}")
    return []


def _parse_size(size_str: str) -> int:
    """Parse human-readable size to bytes."""
    import re
    m = re.match(r'([\d.]+)\s*(GB|MB|KB)', size_str, re.IGNORECASE)
    if not m:
        log.warning(f"Could not parse size string: {size_str}")
        return 0
    val = float(m.group(1))
    unit = m.group(2).upper()
    if unit == "GB":
        return int(val * 1024 * 1024 * 1024)
    elif unit == "MB":
        return int(val * 1024 * 1024)
    elif unit == "KB":
        return int(val * 1024)
    return 0


# ── Torrent Download ─────────────────────────────────────────────────

def _download_torrent(magnet: str, save_dir: str, timeout: int = 7200) -> dict:
    """Download torrent using libtorrent."""
    import libtorrent as lt

    os.makedirs(save_dir, exist_ok=True)
    log.info("  Starting torrent download...")

    ses = lt.session()
    ses.apply_settings({"connections_limit": 200})

    atp = lt.parse_magnet_uri(magnet)
    atp.save_path = save_dir
    handle = ses.add_torrent(atp)
    handle.resume()

    log.info(f"  Torrent name: {handle.name()}")

    start = time.time()
    last_pct = -1
    stalled_count = 0

    while not handle.is_seed():
        s = handle.status()
        pct = s.progress * 100

        # Progress logging every 5%
        if pct - last_pct >= 5 or (time.time() - start) % 60 < 1:
            last_pct = pct
            mb_done = s.total_done / (1024 * 1024)
            mb_total = s.total / (1024 * 1024)
            speed = s.download_rate / (1024 * 1024)
            log.info(
                f"  [{pct:.0f}%] {mb_done:.1f}/{mb_total:.1f} MB | "
                f"{speed:.2f} MB/s | Peers: {s.num_peers}"
            )

        # Timeout check
        if time.time() - start > timeout:
            log.warning(f"  Timeout ({timeout}s) - returning partial download")
            break

        # Stalled detection (2 minutes no speed with peers)
        if s.download_rate < 1024 and s.num_peers > 0:
            stalled_count += 1
            if stalled_count > 120:
                log.warning("  Stalled - no speed for 2 min, waiting more...")
                stalled_count = 0
        else:
            stalled_count = 0

        time.sleep(1)

    # Find largest video file
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".ts", ".m4v"}
    largest = None
    largest_size = 0
    for root, _, files in os.walk(save_dir):
        for f in files:
            if os.path.splitext(f)[1].lower() in video_exts:
                path = os.path.join(root, f)
                sz = os.path.getsize(path)
                if sz > largest_size:
                    largest_size = sz
                    largest = path

    # Lưu lại thông tin trước khi remove
    total_done = handle.status().total_done
    torrent_name = handle.name()
    
    ses.remove_torrent(handle)

    return {
        "success": largest is not None,
        "file_path": largest,
        "file_size": largest_size,
        "downloaded_bytes": total_done,
        "elapsed": time.time() - start,
        "name": torrent_name,
    }


# ── Video Normalizer ─────────────────────────────────────────────────

def _normalize(input_path: str, output_path: str, quality: str, profile: str) -> dict:
    """Normalize video to target quality using FFmpeg."""
    res_map = {
        "4k": ("3840", "2160"),
        "1080p": ("1920", "1080"),
        "720p": ("1280", "720"),
        "480p": ("856", "480"),
    }
    w, h = res_map.get(quality, ("1920", "1080"))

    profiles = {
        "review":     ["libx264", "slow",   "18", "256k"],
        "standard":   ["libx264", "medium", "20", "192k"],
        "compressed": ["libx264", "fast",   "23", "128k"],
        "h265":       ["libx265", "medium", "22", "192k"],
    }
    codec, preset, crf, audio = profiles.get(profile, profiles["standard"])

    # Scale filter (force aspect ratio, pad to exact resolution)
    scale_filter = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
    )

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-movflags", "+faststart",
        "-map", "0:v?", "-map", "0:a?",
        "-c:v", codec, "-preset", preset, "-crf", crf,
        "-vf", scale_filter,
        "-c:a", "aac", "-b:a", audio, "-ac", "2",
        "-c:s", "copy",
        output_path,
    ]

    log.info(f"  Normalizing to {quality} ({profile})...")
    # Chạy FFmpeg mà không capture output để hiển thị tiến trình trực tiếp
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    for line in process.stdout:
        log.info(f"FFmpeg: {line.strip()}")
    process.wait()
    result = process

    if result.returncode != 0:
        log.warning("  FFmpeg error, returning original file")
        return {
            "success": True,
            "output_path": input_path,
            "file_size": os.path.getsize(input_path),
            "codec": "raw",
            "resolution": quality,
        }

    return {
        "success": True,
        "output_path": output_path,
        "file_size": os.path.getsize(output_path),
        "codec": codec,
        "resolution": quality,
    }


# ── Main Pipeline ────────────────────────────────────────────────────

def download_movie(
    title: str,
    output_dir: str = "./downloads",
    quality: str = "1080p",
    profile: str = "review",
    seeders_min: int = 0,
    timeout: int = 7200,
) -> dict:
    """Full pipeline: search → download → normalize.

    Tries YTS first, then 1337x as fallback.
    """
    t0 = time.time()

    log.info("=" * 50)
    log.info(f"StreamPuller | {title}")
    log.info(f"Quality: {quality} | Profile: {profile}")
    log.info("=" * 50)

    # Step 1: Search (YTS first, then 1337x fallback)
    log.info("[1/3] Searching torrents...")
    results = _yts_get(title, quality=quality, limit=10)

    if not results:
        log.info("  YTS returned no results, trying 1337x...")
        results = _1337x_search(title, quality=quality, limit=10)

    if not results:
        log.error("No torrents found on any source!")
        log.error("Tip: try a different title or use magnet link:")
        log.error("  from main import download_by_magnet")
        log.error("  download_by_magnet('magnet:?...', output_dir=...)")
        return {"success": False, "errors": ["No torrents found"]}

    log.info(f"  Found {len(results)} results!")
    for i, m in enumerate(results[:5]):
        bt = m["best_torrent"]
        log.info(
            f"  {i+1}. {m['title']} ({m['year']}) | "
            f"{bt['quality']} | {bt['size']} | Seeds: {bt['seeds']}"
        )

    # Pick best torrent
    candidates = []
    for m in results:
        for t in m["torrents"]:
            if t["seeds"] >= seeders_min or seeders_min == 0:
                candidates.append({
                    **t,
                    "movie_title": m["title"],
                    "movie_year": m["year"],
                })
    if not candidates:
        candidates = [
            {**m["best_torrent"], "movie_title": m["title"], "movie_year": m["year"]}
            for m in results[:1]
        ]
    candidates.sort(key=lambda x: x["seeds"], reverse=True)
    chosen = candidates[0]
    log.info(f"\nSelected: {chosen['movie_title']} | {chosen['quality']} | {chosen['seeds']} seeds")

    # Step 2: Download
    log.info("[2/3] Downloading torrent...")
    dl_dir = os.path.join(output_dir, "_temp")
    dl = _download_torrent(chosen["magnet"], dl_dir, timeout=timeout)

    if not dl["success"] or not dl["file_path"]:
        log.error("Download failed!")
        return {"success": False, "errors": ["Download failed"]}

    log.info(
        f"  Done: {os.path.basename(dl['file_path'])} "
        f"({dl['file_size']/(1024*1024):.1f} MB) in {dl['elapsed']:.0f}s"
    )

    # Step 3: Normalize
    log.info("[3/3] Normalizing to MP4...")
    safe = chosen["movie_title"].replace(" ", "_").replace(":", "_").replace("/", "_")
    out_file = os.path.join(output_dir, f"{safe}_{chosen['quality']}.mp4")
    norm = _normalize(dl["file_path"], out_file, quality, profile)

    # Cleanup temp files
    try:
        import shutil
        shutil.rmtree(dl_dir)
    except Exception as e:
        log.warning(f"Failed to clean up temporary directory {dl_dir}: {e}")

    elapsed = time.time() - t0
    result = {
        "success": norm["success"],
        "output_path": norm["output_path"],
        "file_size": norm["file_size"],
        "resolution": norm["resolution"],
        "codec": norm["codec"],
        "elapsed": elapsed,
        "movie_title": chosen["movie_title"],
        "movie_year": chosen["movie_year"],
    }
    log.info("=" * 50)
    log.info(
        f"COMPLETE | {norm['output_path']} | "
        f"{norm['file_size']/(1024*1024):.1f} MB | {elapsed:.0f}s"
    )
    log.info("=" * 50)
    return result


def download_by_magnet(
    magnet: str,
    output_dir: str = "./downloads",
    output_name: str = None,
    quality: str = "1080p",
    profile: str = "review",
    timeout: int = 7200,
) -> dict:
    """Download directly from magnet link (bypasses search)."""
    log.info("=" * 50)
    log.info(f"StreamPuller | Downloading from magnet link")
    log.info(f"Quality: {quality} | Profile: {profile}")
    log.info("=" * 50)

    dl_dir = os.path.join(output_dir, "_temp")
    dl = _download_torrent(magnet, dl_dir, timeout=timeout)

    if not dl["success"] or not dl["file_path"]:
        log.error("Download failed from magnet link!")
        return {"success": False, "errors": ["Download failed"]}

    if output_name:
        out = os.path.join(output_dir, f"{output_name}.mp4")
    else:
        base = os.path.splitext(os.path.basename(dl["file_path"]))[0]
        out = os.path.join(output_dir, f"{base}.mp4")

    norm = _normalize(dl["file_path"], out, quality, profile)
    try:
        import shutil
        shutil.rmtree(dl_dir)
    except Exception as e:
        log.warning(f"Failed to clean up temporary directory {dl_dir}: {e}")

    return {**norm, "success": norm["success"], "elapsed": dl["elapsed"]}


def search_movie(title: str, quality: str = "all", limit: int = 5) -> list:
    """Search torrents without downloading (YTS + 1337x)."""
    log.info(f"Searching for movie: {title}")
    results = _yts_get(title, quality=quality, limit=limit)
    if not results:
        results = _1337x_search(title, quality=quality, limit=limit)
    return results


# ── Hot Movies Discovery ─────────────────────────────────────────────

def get_hot_movies(limit: int = 10) -> list:
    """Fetches a list of hot movies from YTS API based on seeds."""
    log.info("Fetching hot movies from YTS...")
    params = {
        "sort_by": "seeds",
        "order_by": "desc",
        "limit": limit,
        "genre": "all", # Có thể thêm các bộ lọc khác nếu cần
    }
    for domain in YTS_DOMAINS:
        url = f"https://{domain}/api/v2/list_movies.json"
        try:
            log.debug(f"Attempting to fetch hot movies from {url}")
            r = requests.get(url, params=params, timeout=YTS_TIMEOUT)
            r.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = r.json()
            if data.get("status") == "ok" and data.get("data", {}).get("movie_count", 0) > 0:
                log.info(f"Successfully fetched hot movies from {domain}")
                return data["data"]["movies"]
            else:
                log.warning(f"YTS API from {domain} returned no movies or status not 'ok'. Status: {data.get('status')}")
        except requests.exceptions.RequestException as e:
            log.warning(f"Could not fetch hot movies from {domain}: {e}")
        except json.JSONDecodeError as e:
            log.error(f"Failed to decode JSON from {domain}: {e}")
    log.error("Failed to fetch hot movies from any YTS domain.")
    return []


# ── CLI ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="StreamPuller - Torrent Movie Downloader")
    parser.add_argument("target", nargs="?", help="Movie title or magnet link") # target is now optional
    parser.add_argument("-o", "--output", default="./downloads", help="Output directory")
    parser.add_argument("-q", "--quality", choices=["4k", "1080p", "720p", "480p"], default="1080p")
    parser.add_argument("-p", "--profile", choices=["review", "standard", "compressed", "h265"], default="review")
    parser.add_argument("-s", "--seeders", type=int, default=0)
    parser.add_argument("-t", "--timeout", type=int, default=7200)
    parser.add_argument("-n", "--name", help="Custom output name (magnet only)")
    parser.add_argument("--hot-movies", action="store_true", help="Display a list of hot movies") # New argument
    args = parser.parse_args()

    if args.hot_movies:
        log.info("""\n==================================================")
        log.info("StreamPuller | Hot Movies Discovery")
        log.info("==================================================""")
        movies = get_hot_movies(limit=10)
        if movies:
            log.info("Top 10 Hot Movies:")
            for i, m in enumerate(movies):
                log.info(f"  {i+1}. {m['title']} ({m['year']}) - Rating: {m['rating']}/10")
        else:
            log.info("Could not retrieve hot movies at this time.")
        sys.exit(0)

    if not args.target:
        parser.print_help()
        sys.exit(1)

    if args.target.startswith("magnet:"):
        result = download_by_magnet(
            args.target, args.output, args.name,
            args.quality, args.profile, args.timeout,
        )
    else:
        result = download_movie(
            args.target, args.output, args.quality,
            args.profile, args.seeders, args.timeout,
        )

    if result["success"]:
        log.info(f"\nOK: {result['output_path']} ({result['file_size']/(1024*1024):.1f} MB)")
    else:
        log.error(f"\nFAIL: {result.get('errors', ['Unknown error'])}")
        sys.exit(1)
