from flask import Flask, request, jsonify
import yt_dlp
import subprocess

app = Flask(__name__)

@app.route("/")
def home():
    return "yt-dlp CloudRun is running!"

@app.route("/download", methods=["POST"])
def download():
    data = request.get_json()
    url = data.get("url")

    ydl_opts = {
        "format": "best",
        "outtmpl": "/tmp/%(title)s.%(ext)s",
        "cookiefile": "/app/cookies.txt"  # đường dẫn tới file cookie trong container
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        return jsonify({"status": "ok", "title": info.get("title")})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    
    return jsonify({"status": "ok", "title": info.get("title")})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))  # Cloud Run luôn dùng PORT
    app.run(host="0.0.0.0", port=port)
