
# Hướng dẫn chạy StreamPuller trên Google Colab

Để chạy StreamPuller một cách dễ dàng và hiển thị log chi tiết trên Google Colab, bạn hãy thực hiện theo các bước sau:

### Bước 1: Cài đặt môi trường
Mở một notebook mới trên Colab và chạy đoạn mã sau để cài đặt các thư viện cần thiết:

```python
!apt-get install -y ffmpeg
!pip install libtorrent requests
!git clone https://github.com/dungtrantricreative-ui/StreamPuller.git
%cd StreamPuller
```

### Bước 2: Xem danh sách phim đang hot
Nếu bạn chưa biết nên tải phim gì, hãy chạy lệnh này để xem các phim đang được quan tâm nhiều nhất (dựa trên lượt seeds):

```python
!python main.py --hot-movies
```

### Bước 3: Tải phim tự động
Sau khi chọn được tên phim hoặc có link magnet, bạn có thể chạy lệnh tải. Log sẽ hiển thị chi tiết tiến trình tải torrent và tiến trình chuyển đổi của FFmpeg:

**Tải theo tên phim:**
```python
!python main.py "Tên Phim Bạn Muốn" --quality 1080p
```

**Tải theo link Magnet:**
```python
!python main.py "magnet:?xt=urn:btih:..." --quality 720p
```

### Lưu ý về Log:
*   **Tiến trình Torrent:** Sẽ cập nhật mỗi 5% hoặc mỗi phút một lần.
*   **Tiến trình FFmpeg:** Tôi đã cập nhật mã nguồn để hiển thị trực tiếp các dòng log từ FFmpeg, giúp bạn biết chính xác nó đang xử lý đến đâu thay vì chạy ngầm như trước.
*   **Lỗi:** Nếu có lỗi xảy ra (ví dụ: không tìm thấy phim), chương trình sẽ in ra thông báo lỗi rõ ràng thay vì im lặng.

### Tùy chỉnh nâng cao:
*   `-o` hoặc `--output`: Thư mục lưu phim (mặc định là `./downloads`).
*   `-q` hoặc `--quality`: Chất lượng phim (`4k`, `1080p`, `720p`, `480p`).
*   `-p` hoặc `--profile`: Cấu hình nén (`review`, `standard`, `compressed`, `h265`).
