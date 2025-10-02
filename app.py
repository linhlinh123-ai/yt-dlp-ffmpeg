from flask import Flask, request, jsonify
import subprocess, os, uuid

app = Flask(__name__)

@app.route("/download", methods=["POST"])
def download_video():
    url = request.json.get("url")
    if not url:
        return jsonify({"error": "Missing video URL"}), 400

    video_id = str(uuid.uuid4())
    output_path = f"/tmp/{video_id}.mp4"

    try:
        subprocess.run([
            "yt-dlp", "-f", "bestvideo+bestaudio",
            "--merge-output-format", "mp4",
            "-o", output_path, url
        ], check=True)
        size = os.path.getsize(output_path)
        return jsonify({"status": "done", "file": output_path, "size": size})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
