from flask import Flask, request, jsonify
import yt_dlp
import os
from google.cloud import storage
from datetime import timedelta

app = Flask(__name__)

# Lấy tên bucket từ biến môi trường Cloud Run
BUCKET_NAME = os.environ.get("GCS_BUCKET", "")

def upload_to_gcs(local_path, bucket_name, dest_blob):
    """Upload file lên GCS và trả signed URL 1 giờ"""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(dest_blob)
    blob.upload_from_filename(local_path)
    # Tạo signed URL có hiệu lực 1h
    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=1),
        method="GET"
    )
    return url

@app.route("/")
def home():
    return "yt-dlp CloudRun is running!"

@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True)
    if not data or "url" not in data:
        return jsonify({"status": "error", "message": "Missing 'url' in request"}), 400

    url = data["url"]

    # Cấu hình yt_dlp
    outtmpl = "/tmp/%(id)s.%(ext)s"
    ydl_opts = {
        "format": "best",
        "outtmpl": outtmpl,
        "cookiefile": "/app/cookies.txt",
        "restrictfilenames": True
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)

        # Kiểm tra dung lượng file
        file_size = os.path.getsize(filepath)

        if file_size <= 512 * 1024 * 1024:  # ≤ 512MB
            return jsonify({
                "status": "ok",
                "title": info.get("title"),
                "ext": info.get("ext"),
                "url": url,
                "file_size": file_size,
                "location": "local"
            })
        else:
            if not BUCKET_NAME:
                return jsonify({"status": "error", "message": "GCS_BUCKET not set"}), 500

            dest_blob = os.path.basename(filepath)
            gcs_url = upload_to_gcs(filepath, BUCKET_NAME, dest_blob)

            return jsonify({
                "status": "ok",
                "title": info.get("title"),
                "ext": info.get("ext"),
                "url": url,
                "file_size": file_size,
                "location": "gcs",
                "download_url": gcs_url
            })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Cloud Run sẽ truyền PORT
    app.run(host="0.0.0.0", port=port)
