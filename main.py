#!/usr/bin/env python3
"""
StreamPuller - Torrent Movie Downloader

Auto-search YTS by movie name → download via libtorrent → normalize to MP4.

Usage:
    python main.py "Movie Title" [--quality 1080p] [--profile review]
    python main.py "magnet:?xt=urn:btih:..." [--quality 720p]
"""
import argparse
import logging
import os
import subprocess
import sys
import time

import requests

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

# ── YTS Search with fallback domains ─────────────────────────────────

YTS_DOMAINS = ["yts.lt", "yts.ag", "yts.mx", "yts.bz", "yts.gg"]


def _api_get(url, params, timeout=15):
    """Make API request with retry logic."""
    for attempt in range(2):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception:
            time.sleep(1)
    return None


def _search_yts(query: str, quality: str = "all", limit: int = 10) -> list:
    """Search YTS API for movies across multiple domains."""
    params = {
        "query_term": query,
        "sort_by": "seeds",
        "order_by": "desc",
        "limit": limit,
    }

    data = None
    for domain in YTS_DOMAINS:
        url = f"https://{domain}/api/v2/list_movies.json"
        result = _api_get(url, params)
        if result and result.get("status") == "ok":
            data = result.get("data", {})
            break

    if not data:
        return []

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
                    ),
                })
        if torrents:
            torrents.sort(key=lambda x: x["seeds"], reverse=True)
            movies.append({
                "title": m["title"],
                "year": m["year"],
                "rating": m["rating"],
                "genres": m.get("genres", []),
                "runtime": m.get("runtime", 0),
                "torrents": torrents,
                "best_torrent": torrents[0],
            })
    return movies


# ── Torrent Download ─────────────────────────────────────────────────

def _download_torrent(magnet: str, save_dir: str, timeout: int = 7200) -> dict:
    """Download torrent using libtorrent."""
    import libtorrent as lt

    os.makedirs(save_dir, exist_ok=True)
    log.info("  Downloading torrent...")

    ses = lt.session()
    ses.apply_settings({"connections_limit": 200})

    atp = lt.parse_magnet_uri(magnet)
    atp.save_path = save_dir
    handle = ses.add_torrent(atp)
    handle.resume()

    log.info(f"  Torrent: {handle.name()}")

    start = time.time()
    last_pct = -1
    stalled_count = 0

    while not handle.is_seed():
        s = handle.status()
        pct = s.progress * 100

        # Progress logging
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
            log.warning(f"  Timeout ({timeout}s)")
            break

        # Stalled detection
        if s.download_rate < 1024 and s.num_peers > 0:
            stalled_count += 1
            if stalled_count > 120:  # 2 minutes no speed
                log.warning("  Stalled download, continuing anyway...")
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

    final = handle.status()
    ses.remove_torrent(handle)

    return {
        "success": largest is not None,
        "file_path": largest,
        "file_size": largest_size,
        "downloaded_bytes": final.total_done,
        "elapsed": time.time() - start,
        "name": handle.name(),
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
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)

    if result.returncode != 0:
        log.warning("  FFmpeg error, returning raw file")
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
    """Full pipeline: search → download → normalize."""
    t0 = time.time()

    log.info("=" * 50)
    log.info(f"StreamPuller | {title}")
    log.info(f"Quality: {quality} | Profile: {profile}")
    log.info("=" * 50)

    # Step 1: Search
    log.info("[1/3] Searching torrents...")
    results = _search_yts(title, quality=quality, limit=10)
    if not results:
        log.error("No torrents found!")
        return {"success": False, "errors": ["No torrents found"]}

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
    log.info("[2/3] Downloading...")
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
    log.info("[3/3] Normalizing...")
    safe = chosen["movie_title"].replace(" ", "_").replace(":", "_").replace("/", "_")
    out_file = os.path.join(output_dir, f"{safe}_{chosen['quality']}.mp4")
    norm = _normalize(dl["file_path"], out_file, quality, profile)

    # Cleanup
    try:
        import shutil
        shutil.rmtree(dl_dir)
    except Exception:
        pass

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
    """Download directly from magnet link."""
    dl_dir = os.path.join(output_dir, "_temp")
    dl = _download_torrent(magnet, dl_dir, timeout=timeout)
    if not dl["success"] or not dl["file_path"]:
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
    except Exception:
        pass

    return {**norm, "success": norm["success"], "elapsed": dl["elapsed"]}


def search_movie(title: str, quality: str = "all", limit: int = 5) -> list:
    """Search without downloading."""
    return _search_yts(title, quality=quality, limit=limit)


# ── CLI ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="StreamPuller - Torrent Movie Downloader")
    parser.add_argument("target", help="Movie title or magnet link")
    parser.add_argument("-o", "--output", default="./downloads", help="Output directory")
    parser.add_argument("-q", "--quality", choices=["4k", "1080p", "720p", "480p"], default="1080p")
    parser.add_argument("-p", "--profile", choices=["review", "standard", "compressed", "h265"], default="review")
    parser.add_argument("-s", "--seeders", type=int, default=0)
    parser.add_argument("-t", "--timeout", type=int, default=7200)
    parser.add_argument("-n", "--name", help="Custom output name (magnet only)")
    args = parser.parse_args()

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
        print(f"\nOK: {result['output_path']} ({result['file_size']/(1024*1024):.1f} MB)")
    else:
        print(f"\nFAIL: {result.get('errors')}")
        sys.exit(1)
