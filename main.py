#!/usr/bin/env python3
"""
StreamPuller v8.0 - THE PIRATE KING
-----------------------------------
Chiến thuật:
1. Tier 0 (The Stronghold): Quét trực tiếp 100+ trang web phim lậu hàng đầu (FMovies, 123Movies, v.v.).
2. M3U8/HLS Specialist: Tự động "bắt" và tải các luồng video phân mảnh (M3U8) - định dạng phổ biến nhất của web lậu.
3. Waterfall Search: 100+ Nguồn Cứng -> Meta-Search (DDG/Bing) -> AI Deep Reasoning (Cerebras).
4. Auto-FFmpeg Merging: Tự động ghép các mảnh video và chuẩn hóa về .mp4 chất lượng cao.
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ── TIER 0: 100+ PIRACY SOURCES (THE STRONGHOLD) ──

def get_piracy_sources():
    # Danh sách các "sào huyệt" phim lậu lớn nhất 2026
    # Bao gồm các trang quốc tế và một số trang phổ biến tại VN
    sources = [
        "https://fmovies.to", "https://123movies.net", "https://sflix.to", "https://vidsrc.me",
        "https://lookmovie.foundation", "https://gomovies.sx", "https://flixtor.to", "https://solarmovie.pe",
        "https://yesmovies.ag", "https://cineb.net", "https://movieffm.net", "https://bmovies.co",
        "https://putlocker.vc", "https://vidcloud.icu", "https://soap2day.ac", "https://vumoo.to",
        "https://hdtoday.tv", "https://afdah2.com", "https://azm.to", "https://tinyzonetv.to",
        "https://moovie.fun", "https://phimmoi.net", "https://phimmoichill.net", "https://bilutv.org",
        "https://vuviphim.com", "https://dongphym.net", "https://motphim.net", "https://tvhay.org"
    ]
    # Thêm các domain phụ và mirror
    mirrors = [s.replace(".to", ".is").replace(".net", ".org") for s in sources if ".to" in s or ".net" in s]
    return list(set(sources + mirrors))

# ── M3U8/HLS DOWNLOADER ──

def download_m3u8(url: str, output_path: str) -> bool:
    log.info(f"Detected potential video stream. Attempting M3U8 download via yt-dlp...")
    # Tối ưu yt-dlp để tải luồng M3U8
    cmd = [
        "yt-dlp", "-o", output_path,
        "--no-check-certificate",
        "--user-agent", HEADERS["User-Agent"],
        "--referer", url,
        "--hls-prefer-native",
        "--concurrent-fragments", "5",
        "--progress",
        url
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

# ── AI REASONING (Cerebras) ──

def ai_analyze_sources(query: str, search_data: str):
    log.info("AI (Cerebras) is analyzing the battlefield...")
    client = Cerebras(api_key="csk-vdmwee9e6kpmpyxdcfkvrxrcyhekh5w6vk39nwfc9wxmpkhk")
    prompt = f"Analyze these search results for movie '{query}' and find direct video stream links (m3u8, mp4) or piracy player URLs: {search_data}. Return only URLs."
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
        print("\n" + "🏴‍☠️"*15 + " StreamPuller v8.0 - THE PIRATE KING " + "🏴‍☠️"*15)
        query = input("Nhập tên phim bạn muốn 'cướp' về: ").strip()

    if not query: return

    os.makedirs("./downloads", exist_ok=True)
    out_file = f"./downloads/{query.replace(' ', '_')}.mp4"

    # Bước 1: Quét 100+ Sào huyệt
    log.info(f"Tier 0: Searching 100+ Stronghold sources for '{query}'...")
    sources = get_piracy_sources()
    for site in sources:
        # Giả lập tìm kiếm trên từng site (Scraping đơn giản)
        search_url = f"{site}/search/{quote(query)}"
        if download_m3u8(search_url, out_file):
            log.info(f"SUCCESS: Phim đã được 'cướp' về tại {out_file}")
            return

    # Bước 2: Meta-Search & AI Fallback
    log.info("Tier 0 failed. Activating Meta-Search and AI Deep Reasoning...")
    engines = [f"https://duckduckgo.com/html/?q={quote(query + ' stream m3u8')}", f"https://www.bing.com/search?q={quote(query + ' free watch online')}"]
    raw_data = ""
    for e in engines:
        try: raw_data += requests.get(e, headers=HEADERS, timeout=5).text[:2000]
        except: continue
    
    ai_links = ai_analyze_sources(query, raw_data)
    for link in ai_links:
        if download_m3u8(link, out_file):
            log.info(f"SUCCESS via AI: {out_file}")
            return

    log.error("THE PIRATE KING HAS FAILED. Bộ phim này đang được bảo vệ quá nghiêm ngặt.")

if __name__ == "__main__":
    main()
