from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import yt_dlp
import os
import re
import time
import subprocess

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def sanitize_filename(filename):
    return re.sub(r'[^\w\s.-]', '', filename)

# ========== SERVE INDEX.HTML ==========
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

# ========== DOWNLOAD API ==========
@app.route('/download', methods=['POST'])
def download():
    data = request.json
    url = data.get('url')
    format_type = data.get('format', 'mp4')
    
    if not url:
        return jsonify({'status': 'error', 'message': 'URL tidak boleh kosong'}), 400
    
    try:
        # Hapus file lama di folder downloads (opsional)
        for f in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, f)
            if os.path.isfile(file_path):
                os.remove(file_path)
        
        if format_type == 'mp3':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                'quiet': False,
                'no_warnings': False,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            }
        else:
            ydl_opts = {
                'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
                'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                'quiet': False,
                'no_warnings': False,
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = sanitize_filename(info.get('title', 'video'))
            ext = 'mp3' if format_type == 'mp3' else 'mp4'
            filename = f"{title}.{ext}"
            filepath = os.path.join(DOWNLOAD_FOLDER, filename)
            
            # Cek apakah file benar-benar ada
            if os.path.exists(filepath):
                return jsonify({
                    'status': 'success',
                    'filename': filename,
                    'message': 'Download berhasil!'
                })
            else:
                # Coba cari file lain di folder
                files = os.listdir(DOWNLOAD_FOLDER)
                if files:
                    return jsonify({
                        'status': 'success',
                        'filename': files[0],
                        'message': 'Download berhasil!'
                    })
                else:
                    return jsonify({'status': 'error', 'message': 'File tidak ditemukan'}), 404
                
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/download-file/<filename>')
def download_file(filename):
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({'status': 'error', 'message': 'File tidak ditemukan'}), 404

if __name__ == '__main__':
    print("🚀 Server berjalan di http://localhost:5000")
    print("📱 Buka di browser: http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
