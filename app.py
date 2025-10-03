from flask import Flask, request, jsonify
import yt_dlp
import os
from google.cloud import storage
from datetime import timedelta
import threading
import requests
import uuid
import glob
import logging

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# Bucket GCS lấy từ biến môi trường
BUCKET_NAME = os.environ.get("GCS_BUCKET", "")

def upload_to_gcs(local_path, bucket_name, dest_blob):
    """Upload file lên GCS và trả về public URL"""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(dest_blob)
    blob.upload_from_filename(local_path)

    # nếu bucket đã set public read
    url = f"https://storage.googleapis.com/{bucket_name}/{dest_blob}"
    return url

def _cleanup_tmp_by_id(video_id):
    """Xóa các file tạm liên quan đến id trong /tmp"""
    pattern = f"/tmp/{video_id}*"
    for p in glob.glob(pattern):
        try:
            os.remove(p)
            app.logger.info("Removed tmp file: %s", p)
        except Exception as e:
            app.logger.warning("Failed to remove tmp file %s: %s", p, e)

def process_job(job_id, url, callback_url):
    """Xử lý tải video và callback kết quả về n8n"""
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": "/tmp/%(id)s.%(ext)s",
        "cookiefile": "/app/cookies.txt",
        "merge_output_format": "mp4",
        "postprocessors": [{
            "key": "FFmpegVideoRemuxer",
            "preferedformat": "mp4",   # yt-dlp uses this spelling
        }],
        "restrictfilenames": True,
        "ffmpeg_location": "/usr/bin/ffmpeg",
        # pass -c copy để chỉ remux, không encode lại
        "postprocessor_args": ["-c", "copy"],
        "quiet": False,
        "no_warnings": False,
    }

    result = None
    video_id = None
    filepath = None

    try:
        app.logger.info("Job %s: starting download for %s", job_id, url)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id")
            filepath = ydl.prepare_filename(info)
            app.logger.info("Job %s: downloaded, filepath=%s", job_id, filepath)

        file_size = os.path.getsize(filepath)
        app.logger.info("Job %s: file_size=%d bytes", job_id, file_size)

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
        app.logger.exception("Job %s: failed: %s", job_id, e)
        result = {"status": "error", "job_id": job_id, "message": str(e)}

    finally:
        try:
            if video_id:
                _cleanup_tmp_by_id(video_id)
            elif filepath and os.path.exists(filepath):
                os.remove(filepath)
                app.logger.info("Removed tmp file (fallback): %s", filepath)
        except Exception as cleanup_err:
            app.logger.warning("Cleanup error for job %s: %s", job_id, cleanup_err)

    # Callback kết quả
    try:
        app.logger.info("Job %s: sending callback to %s", job_id, callback_url)
        requests.post(callback_url, json=result, timeout=30)
    except Exception as e:
        app.logger.warning("Job %s: Callback failed: %s", job_id, e)

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

    thread = threading.Thread(target=process_job, args=(job_id, url, callback_url), daemon=True)
    thread.start()

    app.logger.info("Queued job %s for %s (callback=%s)", job_id, url, callback_url)
    return jsonify({"status": "queued", "job_id": job_id})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
