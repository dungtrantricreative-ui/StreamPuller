# StreamPuller v2.1

StreamPuller là một công cụ tải phim tự động từ Torrent (YTS & 1337x) và tự động chuẩn hóa video sang định dạng MP4 chất lượng cao bằng FFmpeg. Phiên bản 2.1 đã được cải tiến mạnh mẽ về hệ thống log và tính năng khám phá phim.

## Các tính năng mới trong v2.1
- **Hệ thống Log chi tiết:** Hiển thị rõ ràng thời gian, tiến trình tải Torrent và đặc biệt là hiển thị trực tiếp log từ FFmpeg.
- **Khám phá Phim Hot:** Tìm kiếm danh sách các phim đang "hot" nhất dựa trên lượt chia sẻ (seeds).
- **Cải thiện độ ổn định:** Xử lý lỗi kết nối, timeout và tự động dọn dẹp file tạm.
- **Tối ưu cho Google Colab:** Dễ dàng cài đặt và chạy trên môi trường đám mây.

## Cài đặt
```bash
sudo apt-get install -y ffmpeg
pip install libtorrent requests
```

## Cách sử dụng
### 1. Xem danh sách phim đang hot
```bash
python main.py --hot-movies
```

### 2. Tải phim theo tên
```bash
python main.py "Inception" --quality 1080p --profile review
```

### 3. Tải phim theo link Magnet
```bash
python main.py "magnet:?xt=urn:btih:..." --quality 720p
```

## Các tùy chọn nâng cao
- `-o`, `--output`: Thư mục lưu kết quả (mặc định: `./downloads`).
- `-q`, `--quality`: Chất lượng video (`4k`, `1080p`, `720p`, `480p`).
- `-p`, `--profile`: Cấu hình nén (`review`, `standard`, `compressed`, `h265`).

## Chạy trên Google Colab
Xem chi tiết tại file [Colab_Guide.md](./Colab_Guide.md).

---
MIT License
