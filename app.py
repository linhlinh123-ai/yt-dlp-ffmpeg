from flask import Flask, request, jsonify
import yt_dlp
import os
from google.cloud import storage
from datetime import timedelta
import threading
import requests
import uuid

app = Flask(__name__)

# Bucket GCS lấy từ biến môi trường
BUCKET_NAME = os.environ.get("GCS_BUCKET", "")

def upload_to_gcs(local_path, bucket_name, dest_blob):
    """Upload file lên GCS và trả signed URL 1h"""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(dest_blob)
    blob.upload_from_filename(local_path)
    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=1),
        method="GET"
    )
    return url

def process_job(job_id, url, callback_url):
    """Xử lý tải video và callback kết quả về n8n"""
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": "/tmp/%(id)s.%(ext)s",
        "cookiefile": "/app/cookies.txt",
        "merge_output_format": "mp4",   # chỉ ghép ra container mp4
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferredformat": "mp4",   # convert container thành mp4
        }],
        "restrictfilenames": True,
        "ffmpeg_location": "/usr/bin/ffmpeg",  # optional, để chắc chắn gọi đúng ffmpeg
        "postprocessor_args": [
            "-c", "copy"   # copy stream, không re-encode
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)

        file_size = os.path.getsize(filepath)

        if file_size <= 512 * 1024 * 1024:
            result = {
                "status": "ok",
                "job_id": job_id,
                "title": info.get("title"),
                "ext": info.get("ext"),
                "url": url,
                "file_size": file_size,
                "location": "local"
            }
        else:
            if not BUCKET_NAME:
                result = {"status": "error", "job_id": job_id, "message": "GCS_BUCKET not set"}
            else:
                dest_blob = os.path.basename(filepath)
                gcs_url = upload_to_gcs(filepath, BUCKET_NAME, dest_blob)
                result = {
                    "status": "ok",
                    "job_id": job_id,
                    "title": info.get("title"),
                    "ext": info.get("ext"),
                    "url": url,
                    "file_size": file_size,
                    "location": "gcs",
                    "download_url": gcs_url
                }

    except Exception as e:
        result = {"status": "error", "job_id": job_id, "message": str(e)}

    # Callback kết quả về n8n
    try:
        requests.post(callback_url, json=result, timeout=30)
    except Exception as e:
        print(f"❌ Callback failed: {e}")

@app.route("/")
def home():
    return "yt-dlp CloudRun is running!"

@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True)
    if not data or "url" not in data or "callback_url" not in data:
        return jsonify({"status": "error", "message": "Missing 'url' or 'callback_url'"}), 400

    url = data["url"]
    callback_url = data["callback_url"]
    job_id = str(uuid.uuid4())

    # chạy job background
    thread = threading.Thread(target=process_job, args=(job_id, url, callback_url))
    thread.start()

    return jsonify({"status": "queued", "job_id": job_id})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
