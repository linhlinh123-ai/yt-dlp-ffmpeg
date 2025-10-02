FROM python:3.11-slim

# Cài ffmpeg và dọn cache cho nhẹ image
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Tạo thư mục app
WORKDIR /app

# Copy requirements trước (để cache tốt hơn)
COPY requirements.txt .

# Cài dependencies Python
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code (app.py, cookies.txt sẽ có sẵn từ GitHub Actions)
COPY . .

# Cloud Run yêu cầu port từ biến môi trường PORT
ENV PORT=8080

# Expose port (không bắt buộc nhưng tốt để test local)
EXPOSE 8080

# Chạy app
CMD ["python", "app.py"]
