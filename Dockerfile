FROM python:3.11-slim

# Cài ffmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Copy file requirements.txt và cài đặt
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code
COPY . .

CMD ["python", "app.py"]
