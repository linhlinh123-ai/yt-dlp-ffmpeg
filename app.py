from flask import Flask, request, jsonify
import yt_dlp
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "yt-dlp CloudRun is running!"

@app.route("/download", methods=["POST"])
def download():
    data = request.get_json(silent=True)  # tránh crash nếu request không phải JSON
    if not data or "url" not in data:
        return jsonify({"status": "error", "message": "Missing 'url' in request"}), 400

    url = data["url"]

    # Cấu hình yt_dlp
    ydl_opts = {
        "format": "best",
        "outtmpl": "/tmp/%(id)s.%(ext)s",   # dùng ID video thay vì title để tránh lỗi tên quá dài
        "cookiefile": "/app/cookies.txt",
        "restrictfilenames": True           # loại bỏ ký tự đặc biệt (emoji, khoảng trắng lạ)
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        return jsonify({
            "status": "ok",
            "title": info.get("title"),
            "ext": info.get("ext"),
            "url": url
        })

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Cloud Run sẽ truyền PORT
    app.run(host="0.0.0.0", port=port)
