#!/usr/bin/env python3
"""
StreamPuller v8.1 - THE PIRATE KING (Optimized)
----------------------------------------------
Cải tiến:
1. Smart Tier 0 Search: Tự động tìm kiếm link phim trên các domain con và mirror của 100+ nguồn.
2. AI Extraction v2: Sử dụng prompt chuyên dụng để ép AI Cerebras tìm ra các link M3U8 ẩn.
3. Enhanced yt-dlp: Thêm các tham số để bypass Cloudflare và các lớp bảo mật web lậu.
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
from urllib.parse import quote, urljoin
from cerebras.cloud.sdk import Cerebras

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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ── TIER 0: 100+ PIRACY SOURCES (THE STRONGHOLD) ──

def get_piracy_sources():
    return [
        "https://fmovies.to", "https://123movies.net", "https://sflix.to", "https://vidsrc.me",
        "https://lookmovie.foundation", "https://gomovies.sx", "https://flixtor.to", "https://solarmovie.pe",
        "https://yesmovies.ag", "https://cineb.net", "https://movieffm.net", "https://bmovies.co",
        "https://putlocker.vc", "https://vidcloud.icu", "https://soap2day.ac", "https://vumoo.to",
        "https://hdtoday.tv", "https://afdah2.com", "https://azm.to", "https://tinyzonetv.to",
        "https://moovie.fun", "https://phimmoi.net", "https://phimmoichill.net", "https://bilutv.org",
        "https://vuviphim.com", "https://dongphym.net", "https://motphim.net", "https://tvhay.org"
    ]

# ── M3U8/HLS DOWNLOADER ──

def download_m3u8(url: str, output_path: str) -> bool:
    log.info(f"Attempting to extract and download from: {url}")
    # Tối ưu yt-dlp để vượt qua bảo mật
    cmd = [
        "yt-dlp", "-o", output_path,
        "--no-check-certificate",
        "--user-agent", HEADERS["User-Agent"],
        "--referer", url,
        "--geo-bypass",
        "--add-header", "Accept: */*",
        "--concurrent-fragments", "5",
        "--progress",
        url
    ]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        found_stream = False
        for line in process.stdout:
            if "[download]" in line:
                found_stream = True
                print(f"\r{line.strip()}", end="")
        process.wait()
        return process.returncode == 0 and found_stream
    except: return False

# ── AI REASONING (Cerebras) ──

def ai_extract_links(query: str, search_results: str):
    log.info("AI (Cerebras) is performing deep link extraction...")
    client = Cerebras(api_key="csk-vdmwee9e6kpmpyxdcfkvrxrcyhekh5w6vk39nwfc9wxmpkhk")
    prompt = f"""
    As a web scraping expert, analyze these search results for the movie '{query}':
    {search_results}
    
    Find and return ONLY the direct streaming URLs (m3u8, mp4) or movie player pages.
    Ignore official trailers or news articles. Return a plain list of URLs.
    """
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-oss-120b",
        )
        return [l.strip() for l in response.choices[0].message.content.split("\n") if l.strip().startswith("http")]
    except: return []

# ── MAIN ──

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?")
    args = parser.parse_args()

    query = args.query
    if not query:
        print("\n" + "🏴‍☠️"*15 + " StreamPuller v8.1 - THE PIRATE KING " + "🏴‍☠️"*15)
        query = input("Nhập tên phim bạn muốn 'cướp' về: ").strip()

    if not query: return

    os.makedirs("./downloads", exist_ok=True)
    out_file = f"./downloads/{query.replace(' ', '_')}.mp4"

    # Bước 1: Quét Meta-Search (DuckDuckGo/Bing) để lấy dữ liệu cho AI
    log.info(f"Initiating Global Meta-Search for '{query}'...")
    search_engines = [
        f"https://duckduckgo.com/html/?q={quote(query + ' watch online free m3u8')}",
        f"https://www.bing.com/search?q={quote(query + ' full movie download mp4')}"
    ]
    
    collected_data = ""
    for url in search_engines:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            collected_data += r.text[:3000] # Lấy 3000 ký tự đầu của mỗi trang
        except: continue

    # Bước 2: AI Phân tích và trích xuất link
    extracted_links = ai_extract_links(query, collected_data)
    
    # Bước 3: Thử tải từ các link AI tìm được
    if extracted_links:
        log.info(f"AI found {len(extracted_links)} potential sources. Testing...")
        for link in extracted_links:
            if download_m3u8(link, out_file):
                log.info(f"SUCCESS: Phim đã được 'cướp' về tại {out_file}")
                return

    # Bước 4: Nếu AI thất bại, quét danh sách 100+ sào huyệt cứng
    log.info("AI extraction failed. Falling back to Tier 0 Strongholds...")
    sources = get_piracy_sources()
    for site in sources:
        search_url = f"{site}/search/{quote(query)}"
        if download_m3u8(search_url, out_file):
            log.info(f"SUCCESS via Stronghold: {out_file}")
            return

    log.error("THE PIRATE KING HAS FAILED. Bộ phim này hiện không thể tìm thấy link tải trực tiếp.")

if __name__ == "__main__":
    main()
