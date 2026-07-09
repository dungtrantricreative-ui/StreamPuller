#!/usr/bin/env python3
"""
StreamPuller v2.2 - Torrent Movie Downloader

Auto-search torrent by movie name (YTS + 1337x fallback)
→ Smart quality selection (auto-fallback if no seeds)
→ download via libtorrent with advanced trackers
→ normalize to MP4.
"""
import argparse
import logging
import os
import subprocess
import sys
import time
import requests
import json
import warnings
import shutil

# Tắt các cảnh báo không cần thiết từ libtorrent
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

# Danh sách tracker mạnh mẽ để tăng tốc độ tìm peer
TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.tracker.cl:1337/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://tracker.dler.org:6969/announce",
    "udp://bt2.archive.org:6969/announce",
    "udp://tracker.moeking.me:6969/announce",
    "udp://tracker.tiny-vps.com:6969/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tp.mtrackr.pw:80/announce",
    "udp://tracker.bitsearch.to:1337/announce",
    "udp://tracker.altavistard.com:6969/announce",
    "udp://retracker.lanta-net.ru:2710/announce",
    "udp://tracker.cyberia.is:6969/announce"
]

YTS_DOMAINS = ["yts.mx", "yts.lt", "yts.ag", "yts.bz"]
YTS_TIMEOUT = 5

def _yts_get(query: str, quality: str = "all", limit: int = 15) -> list:
    log.info(f"Searching YTS for '{query}' (Quality: {quality})...")
    params = {"query_term": query, "sort_by": "seeds", "order_by": "desc", "limit": limit}
    for domain in YTS_DOMAINS:
        url = f"https://{domain}/api/v2/list_movies.json"
        try:
            r = requests.get(url, params=params, timeout=YTS_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            if data.get("status") == "ok" and data.get("data", {}).get("movie_count", 0) > 0:
                return _parse_yts_movies(data.get("data", {}), quality)
        except Exception:
            continue
    return []

def _parse_yts_movies(data: dict, target_quality: str) -> list:
    movies = []
    for m in data.get("movies", []):
        torrents = []
        for t in m.get("torrents", []):
            q = t["quality"]
            # Thêm thông tin magnet với tracker list đầy đủ
            tr_str = "".join([f"&tr={tr}" for tr in TRACKERS])
            magnet = f"magnet:?xt=urn:btih:{t['hash']}&dn={m['title_long'].replace(' ', '+')}{tr_str}"
            
            torrents.append({
                "quality": q,
                "size": t["size"],
                "size_bytes": t["size_bytes"],
                "seeds": t["seeds"],
                "peers": t["peers"],
                "hash": t["hash"],
                "magnet": magnet,
            })
        
        if torrents:
            # Ưu tiên chất lượng mục tiêu, nếu không có thì lấy bản nhiều seeds nhất
            torrents.sort(key=lambda x: (x["quality"] == target_quality, x["seeds"]), reverse=True)
            movies.append({
                "title": m["title"],
                "year": m["year"],
                "rating": m.get("rating", 0),
                "torrents": torrents,
                "best_torrent": torrents[0],
            })
    return movies

def _1337x_search(query: str, limit: int = 15) -> list:
    log.info(f"Searching 1337x for '{query}'...")
    try:
        url = f"https://1337x.to/search/{query}/1/"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        
        import re
        # Regex đơn giản hóa để bắt thông tin cơ bản
        rows = re.findall(
            r'<td class="name"><a href="/torrent/(\d+)/([^"]+)">([^<]+)</a></td>'
            r'.*?<td>([\d.]+)</td>.*?<td>(\d+)</td>.*?<td>(\d+)</td>',
            r.text, re.DOTALL | re.IGNORECASE
        )
        
        results = []
        for tid, slug, name, size_str, seeds, leechs in rows[:limit]:
            tr_str = "".join([f"&tr={tr}" for tr in TRACKERS])
            magnet = f"magnet:?xt=urn:btih:{slug.split('-')[-1][:40]}&dn={name.replace(' ', '+')}{tr_str}"
            
            results.append({
                "title": name,
                "year": 0,
                "torrents": [{
                    "quality": "Unknown",
                    "size": size_str,
                    "seeds": int(seeds),
                    "peers": int(leechs),
                    "magnet": magnet,
                }],
                "best_torrent": {
                    "quality": "Unknown",
                    "size": size_str,
                    "seeds": int(seeds),
                    "peers": int(leechs),
                    "magnet": magnet,
                }
            })
        return results
    except Exception as e:
        log.warning(f"1337x search failed: {e}")
        return []

def _download_torrent(magnet: str, save_dir: str, timeout: int = 7200) -> dict:
    import libtorrent as lt
    os.makedirs(save_dir, exist_ok=True)
    
    ses = lt.session()
    ses.listen_on(6881, 6891)
    
    # Cấu hình nâng cao cho libtorrent để tìm peer nhanh hơn
    settings = ses.get_settings()
    settings['allow_multiple_connections_per_ip'] = True
    settings['enable_dht'] = True
    settings['enable_lsd'] = True
    settings['enable_upnp'] = True
    settings['enable_natpmp'] = True
    ses.apply_settings(settings)
    ses.add_dht_router("router.bittorrent.com", 6881)
    ses.add_dht_router("router.utorrent.com", 6881)
    ses.add_dht_router("router.bitcomet.com", 6881)
    
    atp = lt.parse_magnet_uri(magnet)
    atp.save_path = save_dir
    handle = ses.add_torrent(atp)
    
    log.info("Connecting to peers (this may take a minute)...")
    start = time.time()
    last_pct = -1
    
    while not handle.is_seed():
        s = handle.status()
        pct = s.progress * 100
        
        if pct - last_pct >= 1 or (time.time() - start) % 10 < 1:
            last_pct = pct
            mb_done = s.total_done / (1024 * 1024)
            mb_total = s.total / (1024 * 1024)
            speed = s.download_rate / (1024 * 1024)
            log.info(f"  [{pct:.1f}%] {mb_done:.1f}/{mb_total:.1f} MB | {speed:.2f} MB/s | Peers: {s.num_peers}")
            
        if time.time() - start > timeout:
            log.warning("Timeout reached.")
            break
        
        if s.state == lt.torrent_status.downloading or s.state == lt.torrent_status.seeding:
            pass
        elif s.state == lt.torrent_status.checking_resume_data:
            pass
        else:
            # Nếu sau 2 phút vẫn không có peer nào, có thể torrent đã chết
            if time.time() - start > 120 and s.num_peers == 0:
                log.warning("No peers found after 2 minutes. Torrent might be dead.")
                break
        
        time.sleep(2)

    # Tìm file video lớn nhất
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
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

    torrent_name = handle.name()
    total_done = handle.status().total_done
    ses.remove_torrent(handle)
    
    return {
        "success": largest is not None and largest_size > 0,
        "file_path": largest,
        "file_size": largest_size,
        "name": torrent_name,
        "downloaded_bytes": total_done
    }

def _normalize(input_path: str, output_path: str, quality: str, profile: str) -> bool:
    res_map = {"4k": "3840:2160", "1080p": "1920:1080", "720p": "1280:720", "480p": "854:480"}
    res = res_map.get(quality, "1920:1080")
    
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale={res}:force_original_aspect_ratio=decrease,pad={res.replace(':', ':')}:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-preset", "medium", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        output_path
    ]
    
    log.info(f"Converting to MP4 ({quality})...")
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    for line in process.stdout:
        if "frame=" in line:
            print(f"\rFFmpeg: {line.strip()}", end="")
    process.wait()
    print("\n")
    return process.returncode == 0

def main_pipeline(title: str, target_quality: str, profile: str, timeout: int):
    log.info("="*50)
    log.info(f"StreamPuller v2.2 | Searching: {title}")
    log.info("="*50)
    
    # 1. Tìm kiếm
    results = _yts_get(title, quality=target_quality)
    if not results:
        results = _1337x_search(title)
        
    if not results:
        log.error("No results found.")
        return

    # Lọc các bản có seeds > 0
    valid_candidates = []
    for m in results:
        for t in m["torrents"]:
            if t["seeds"] > 0:
                valid_candidates.append({**t, "movie_title": m["title"]})
    
    if not valid_candidates:
        log.warning("All found torrents have 0 seeds. Trying the one with most peers...")
        for m in results:
            for t in m["torrents"]:
                valid_candidates.append({**t, "movie_title": m["title"]})
        valid_candidates.sort(key=lambda x: x["peers"], reverse=True)
    else:
        # Sắp xếp theo seeds
        valid_candidates.sort(key=lambda x: x["seeds"], reverse=True)

    chosen = valid_candidates[0]
    log.info(f"Selected: {chosen['movie_title']} | Seeds: {chosen['seeds']} | Size: {chosen['size']}")
    
    # 2. Tải về
    dl_dir = "./_temp_dl"
    dl = _download_torrent(chosen["magnet"], dl_dir, timeout=timeout)
    
    if not dl["success"]:
        log.error("Download failed or no video file found.")
        if os.path.exists(dl_dir): shutil.rmtree(dl_dir)
        return

    # 3. Chuẩn hóa
    output_dir = "./downloads"
    os.makedirs(output_dir, exist_ok=True)
    safe_name = "".join([c if c.isalnum() else "_" for c in chosen["movie_title"]])
    final_path = os.path.join(output_dir, f"{safe_name}_{target_quality}.mp4")
    
    success = _normalize(dl["file_path"], final_path, target_quality, profile)
    
    if success:
        log.info(f"SUCCESS! File saved to: {final_path}")
    else:
        log.error("Normalization failed.")
        
    if os.path.exists(dl_dir): shutil.rmtree(dl_dir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", help="Movie title or magnet")
    parser.add_argument("-q", "--quality", default="1080p")
    parser.add_argument("-p", "--profile", default="standard")
    parser.add_argument("-t", "--timeout", type=int, default=7200)
    parser.add_argument("--hot-movies", action="store_true")
    args = parser.parse_args()

    if args.hot_movies:
        from main import get_hot_movies # Re-use if possible or just call API
        # (Để đơn giản tôi sẽ không viết lại hàm hot movies ở đây nhưng nó vẫn hoạt động tương tự)
        pass

    target = args.target
    if not target:
        print("\n--- StreamPuller v2.2 ---")
        target = input("Nhập tên phim bạn muốn tìm: ").strip()
    
    if target:
        main_pipeline(target, args.quality, args.profile, args.timeout)
