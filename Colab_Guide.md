# Hướng dẫn chạy StreamPuller v6.0 trên Google Colab

Để sử dụng phiên bản AI-Powered v6.0, bạn hãy làm theo các bước sau:

### Bước 1: Clone mã nguồn
```python
!git clone https://github.com/dungtrantricreative-ui/StreamPuller
%cd StreamPuller
```

### Bước 2: Cài đặt thư viện (Bắt buộc)
```python
!pip install -r requirements.txt
!apt-get install -y ffmpeg
```

### Bước 3: Chạy chương trình
Bạn có thể chạy theo 2 cách:

**Cách 1: Chế độ tương tác (Hỏi tên phim)**
```python
!python main.py
```

**Cách 2: Nhập tên phim trực tiếp**
```python
!python main.py "Tên Phim Năm"
```

**Cách 3: Tải từ link web phim lậu**
```python
!python main.py "https://link-web-phim.com/phim-abc"
```

### Lưu ý:
- Nên nhập tên phim bằng tiếng Anh để AI tìm kiếm hiệu quả nhất.
- Phim tải về sẽ nằm trong thư mục `downloads`.
