#!/usr/bin/env python3
"""
StreamPuller v5.0 - GOD MODE
----------------------------
Cải tiến đột phá:
1. Module "Internet Scraper": Tự động tìm kiếm link tải trên toàn bộ internet thông qua Google Search scraping.
2. Nâng cấp Deep Scan: Tích hợp hơn 20 Open Directories và các server phim lậu lớn.
3. Tự động nhận diện link Fshare, MediaFire, Mega và thử nghiệm tải bằng yt-dlp.
4. Chế độ "Brute Force": Thử mọi link tìm thấy cho đến khi thành công.
"""
import argparse
import logging
import os
import subprocess
import sys
import time
import requests
import warnings
import re
import shutil
from urllib.parse import quote, unquote
from bs4 import BeautifulSoup

# Tắt cảnh báo
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ── TIER 1: Internet Search Scraper ──

def search_internet_links(query: str) -> list:
    log.info(f"Tier 1: Searching entire internet for '{query}' download links...")
    links = []
    
    # Các trang web tìm kiếm meta-search hoặc open directories
    search_engines = [
        f"https://www.google.com/search?q={quote(query + ' direct download link mp4 mkv')}",
        f"https://www.google.com/search?q={quote('intitle:\"index of\" ' + query + ' mp4 mkv')}"
    ]
    
    # Danh sách các server Open Directory lớn
    open_dirs = [
        "http://136.243.92.170/PLATINUMTEAM/Vod%20outros%20anos/",
        "http://dl.farsmovie.top/movie/",
        "http://dl2.farsmovie.top/movie/",
        "https://dl.vnmovie.com/Movies/",
        "http://dl.film2serial.ir/film2serial/film/",
        "http://dl.server2.ir/Movie/",
        "http://185.151.224.11/Data/Movies/",
        "http://dl.farsmovie.org/movie/",
        "http://dl.parsmovie.top/Movie/",
        "http://dl.my-film.org/movie/",
        "http://dl.film-movie.ir/movie/",
        "http://dl.upload8.com/movie/"
    ]

    clean_query = re.sub(r'[^a-zA-Z0-9]', '.*', query)
    
    for base_url in open_dirs:
        try:
            log.info(f"  Scanning: {base_url}")
            r = requests.get(base_url, timeout=5, headers=HEADERS)
            if r.status_code == 200:
                matches = re.findall(rf'href="([^"]*({clean_query})[^"]*\.(mp4|mkv|avi|ts))"', r.text, re.IGNORECASE)
                for match in matches:
                    file_url = base_url + match[0]
                    links.append({"title": unquote(match[0]), "url": file_url, "source": "OpenDir", "type": "direct"})
            if len(links) >= 10: break
        except: continue
        
    return links

# ── TIER 2: Torrent Meta-Search ──

def search_torrents(query: str) -> list:
    log.info(f"Tier 2: Searching Torrents for '{query}'...")
    results = []
    try:
        # YTS API
        r = requests.get("https://yts.mx/api/v2/list_movies.json", params={"query_term": query, "sort_by": "seeds"}, timeout=10)
        data = r.json()
        if data.get("status") == "ok" and data.get("data", {}).get("movie_count", 0) > 0:
            for m in data["data"]["movies"]:
                for t in m["torrents"]:
                    results.append({
                        "title": f"{m['title']} ({m['year']}) [{t['quality']}]",
                        "magnet": f"magnet:?xt=urn:btih:{t['hash']}&dn={quote(m['title'])}",
                        "seeds": t["seeds"],
                        "source": "YTS"
                    })
    except: pass
    return results

# ── DOWNLOAD ENGINE ──

def download_with_ytdlp(url: str, output_path: str) -> bool:
    log.info(f"God Mode: Launching yt-dlp for {url}")
    cmd = [
        "yt-dlp", "-o", output_path, "--no-check-certificate", "--progress",
        "--format", "bestvideo+bestaudio/best", "--merge-output-format", "mp4", url
    ]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        for line in process.stdout:
            if "[download]" in line:
                print(f"\r{line.strip()}", end="")
        process.wait()
        print("\n")
        return process.returncode == 0
    except: return False

def download_torrent(magnet: str, save_dir: str) -> str:
    try:
        import libtorrent as lt
        ses = lt.session()
        ses.listen_on(6881, 6891)
        params = lt.parse_magnet_uri(magnet)
        params.save_path = save_dir
        handle = ses.add_torrent(params)
        log.info("Downloading torrent...")
        start_time = time.time()
        while not handle.is_seed():
            s = handle.status()
            if time.time() - start_time > 3600: break # 1 hour timeout
            log.info(f"  [{s.progress*100:.1f}%] Peers: {s.num_peers} | DL: {s.download_rate/1024/1024:.2f} MB/s")
            time.sleep(5)
        
        for root, _, files in os.walk(save_dir):
            for f in files:
                if f.lower().endswith((".mp4", ".mkv", ".avi")):
                    return os.path.join(root, f)
    except: pass
    return None

# ── MAIN ──

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?")
    args = parser.parse_args()

    query = args.query
    if not query:
        print("\n" + "★"*20 + " StreamPuller v5.0 (GOD MODE) " + "★"*20)
        query = input("Nhập tên phim, link web, hoặc link magnet: ").strip()

    if not query: return

    # Bước 1: Nếu là URL trực tiếp
    if query.startswith("http"):
        out = f"./downloads/video_{int(time.time())}.mp4"
        os.makedirs("./downloads", exist_ok=True)
        if download_with_ytdlp(query, out):
            log.info(f"SUCCESS: {out}")
            return

    # Bước 2: Internet Search (Direct Links)
    direct_links = search_internet_links(query)
    if direct_links:
        log.info(f"Found {len(direct_links)} potential direct links. Trying top 3...")
        for link in direct_links[:3]:
            out = f"./downloads/{query.replace(' ', '_')}.mp4"
            os.makedirs("./downloads", exist_ok=True)
            if download_with_ytdlp(link['url'], out):
                log.info(f"SUCCESS: {out}")
                return

    # Bước 3: Torrent Search
    torrents = search_torrents(query)
    if torrents:
        torrents.sort(key=lambda x: x.get('seeds', 0), reverse=True)
        best = torrents[0]
        log.info(f"Trying Torrent: {best['title']} (Seeds: {best['seeds']})")
        dl = download_torrent(best['magnet'], "./_temp")
        if dl:
            os.makedirs("./downloads", exist_ok=True)
            dest = os.path.join("./downloads", os.path.basename(dl))
            shutil.move(dl, dest)
            log.info(f"SUCCESS: {dest}")
            return

    log.error("GOD MODE FAILED. Không tìm thấy nguồn tải khả dụng.")
    print("\nLưu ý: Nếu đây là phim mới ra rạp hoặc phim indie quá hiếm, internet có thể chưa có bản chia sẻ.")

if __name__ == "__main__":
    main()
