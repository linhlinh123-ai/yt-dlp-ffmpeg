FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg && \
    pip install --no-cache-dir -r requirements.txt

WORKDIR /app
COPY . .

CMD ["python", "app.py"]
