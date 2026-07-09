# Hướng dẫn chạy StreamPuller v3.0 trên Google Colab

Phiên bản 3.0 tích hợp **yt-dlp** giúp tải phim từ các nguồn link trực tiếp (Direct Link), khắc phục triệt để vấn đề Torrent không có seeds.

### Bước 1: Cài đặt môi trường (Chạy 1 lần duy nhất)
Copy và chạy đoạn code sau trong một cell của Colab:

```python
# 1. Cài đặt các thư viện Python cần thiết
!pip install yt-dlp libtorrent requests

# 2. Cài đặt công cụ hệ thống (FFmpeg)
!apt-get update
!apt-get install -y ffmpeg
```

### Bước 2: Tải mã nguồn
Nếu bạn chưa clone repository:
```bash
!git clone https://github.com/dungtrantricreative-ui/StreamPuller
%cd StreamPuller
```

### Bước 3: Chạy công cụ
Bạn chỉ cần chạy lệnh sau và nhập tên phim khi được hỏi:
```python
!python main.py
```

**Hoặc chạy kèm tên phim để tự động hóa:**
```python
!python main.py "Spider-Man Homecoming"
```

### Tại sao nên dùng v3.0?
- **Tốc độ:** Tải trực tiếp từ server phim nên thường đạt tốc độ tối đa của đường truyền.
- **Chắc chắn:** Không phụ thuộc vào số lượng người đang chia sẻ (seeds) như Torrent.
- **Tự động:** Tool sẽ tự tìm link trực tiếp trước, nếu không có mới chuyển sang tìm Torrent.
- **Log chi tiết:** Hiển thị rõ ràng tiến trình tải từng % một.
