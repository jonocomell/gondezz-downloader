from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import yt_dlp
import os
import re
import time
import json
import subprocess
import shutil
from datetime import datetime
import threading
import queue

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ========== KONFIGURASI ==========
DOWNLOAD_FOLDER = "downloads"
HISTORY_FILE = "history.json"
SETTINGS_FILE = "settings.json"
TEMP_FOLDER = "temp"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)

# ========== QUEUE DOWNLOAD ==========
download_queue = queue.Queue()
download_status = {}
download_progress = {}

# ========== FUNGSI SANITASI ==========
def sanitize_filename(filename):
    return re.sub(r'[^\w\s.-]', '', filename)

# ========== FUNGSI HISTORY ==========
def save_history(url, filename, platform, format_type, resolution, size="0 MB"):
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            try:
                history = json.load(f)
            except:
                history = []
    
    history.append({
        'url': url,
        'filename': filename,
        'platform': platform,
        'format': format_type,
        'resolution': resolution,
        'size': size,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    
    # Simpan hanya 100 history terakhir
    if len(history) > 100:
        history = history[-100:]
    
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=4)

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def clear_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)

# ========== FUNGSI SETTINGS ==========
def load_settings():
    default = {
        'theme': 'dark',
        'download_folder': 'downloads',
        'auto_rename': False,
        'compress': False,
        'proxy': '',
        'notifications': True
    }
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            try:
                return json.load(f)
            except:
                return default
    return default

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)

# ========== DETEKSI PLATFORM ==========
def detect_platform(url):
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'YouTube'
    elif 'instagram.com' in url:
        return 'Instagram'
    elif 'tiktok.com' in url or 'vt.tiktok.com' in url:
        return 'TikTok'
    elif 'facebook.com' in url or 'fb.watch' in url:
        return 'Facebook'
    elif 'twitter.com' in url or 'x.com' in url:
        return 'Twitter/X'
    elif 'whatsapp.com' in url:
        return 'WhatsApp'
    elif 'pinterest.com' in url:
        return 'Pinterest'
    else:
        return 'Unknown'

# ========== GET FILE SIZE ==========
def get_file_size(filepath):
    try:
        size = os.path.getsize(filepath)
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size/(1024*1024):.1f} MB"
        else:
            return f"{size/(1024*1024*1024):.1f} GB"
    except:
        return "0 MB"

# ========== COMPRESS VIDEO ==========
def compress_video(input_path, output_path):
    try:
        cmd = [
            'ffmpeg', '-i', input_path,
            '-vf', 'scale=720:-2',
            '-c:v', 'libx264',
            '-crf', '28',
            '-preset', 'fast',
            '-c:a', 'aac',
            '-b:a', '128k',
            output_path
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        return os.path.exists(output_path)
    except:
        return False

# ========== CONVERT TO GIF ==========
def convert_to_gif(input_path, output_path):
    try:
        cmd = [
            'ffmpeg', '-i', input_path,
            '-vf', 'fps=10,scale=320:-1:flags=lanczos',
            '-c:v', 'gif',
            '-loop', '0',
            output_path
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        return os.path.exists(output_path)
    except:
        return False

# ========== TRIM VIDEO ==========
def trim_video(input_path, output_path, start_time, end_time):
    try:
        cmd = [
            'ffmpeg', '-i', input_path,
            '-ss', start_time,
            '-to', end_time,
            '-c', 'copy',
            output_path
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        return os.path.exists(output_path)
    except:
        return False

# ========== ROUTES ==========
@app.route('/')
def index():
    return send_from_directory('.', 'indexV2.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'GET':
        return jsonify(load_settings())
    else:
        data = request.json
        save_settings(data)
        return jsonify({'status': 'success'})

@app.route('/history')
def history():
    return jsonify(load_history())

@app.route('/clear-history', methods=['POST'])
def clear_history_route():
    clear_history()
    return jsonify({'status': 'success'})

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    url = data.get('url')
    format_type = data.get('format', 'mp4')
    resolution = data.get('resolution', '720')
    is_playlist = data.get('playlist', False)
    is_gif = data.get('gif', False)
    is_compress = data.get('compress', False)
    trim_start = data.get('trim_start', '')
    trim_end = data.get('trim_end', '')
    auto_rename = data.get('auto_rename', False)

    if not url:
        return jsonify({'status': 'error', 'message': 'URL tidak boleh kosong'}), 400

    try:
        # Hapus file lama
        for f in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, f)
            if os.path.isfile(file_path):
                os.remove(file_path)

        platform = detect_platform(url)
        settings = load_settings()
        
        # Proxy support
        proxy = settings.get('proxy', '')
        
        # ===== PENGATURAN YT-DLP =====
        ydl_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'extract_flat': False,
        }
        
        if proxy:
            ydl_opts['proxy'] = proxy

        # ===== RESOLUSI =====
        if format_type == 'mp3':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            if is_gif:
                ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best[height<=720]'
            else:
                res_map = {
                    '144': 'bestvideo[height<=144]+bestaudio/best[height<=144]',
                    '360': 'bestvideo[height<=360]+bestaudio/best[height<=360]',
                    '720': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
                    '1080': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
                }
                ydl_opts['format'] = res_map.get(resolution, 'bestvideo[height<=720]+bestaudio/best[height<=720]')

        # ===== PLAYLIST =====
        if is_playlist and platform == 'YouTube':
            ydl_opts['extract_flat'] = False
            ydl_opts['ignoreerrors'] = True

        # ===== INSTAGRAM =====
        if platform == 'Instagram':
            ydl_opts['format'] = 'best'

        # ===== WHATSAPP =====
        if platform == 'WhatsApp':
            ydl_opts['format'] = 'best'

        # ===== EKSEKUSI DOWNLOAD =====
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if is_playlist and platform == 'YouTube':
                entries = info.get('entries', [])
                if entries:
                    filenames = []
                    for entry in entries:
                        title = sanitize_filename(entry.get('title', 'video'))
                        ext = 'mp3' if format_type == 'mp3' else 'mp4'
                        filename = f"{title}.{ext}"
                        filenames.append(filename)
                        
                        if auto_rename:
                            new_name = f"gondezz_{int(time.time())}_{filename}"
                            old_path = os.path.join(DOWNLOAD_FOLDER, filename)
                            new_path = os.path.join(DOWNLOAD_FOLDER, new_name)
                            if os.path.exists(old_path):
                                os.rename(old_path, new_path)
                                filename = new_name
                        
                        size = get_file_size(os.path.join(DOWNLOAD_FOLDER, filename))
                        save_history(url, filename, 'YouTube Playlist', format_type, resolution, size)
                    
                    return jsonify({
                        'status': 'success',
                        'filenames': filenames,
                        'message': f'Playlist berhasil! ({len(filenames)} video)'
                    })
            
            title = sanitize_filename(info.get('title', 'video'))
            ext = 'mp3' if format_type == 'mp3' else 'mp4'
            filename = f"{title}.{ext}"
            filepath = os.path.join(DOWNLOAD_FOLDER, filename)

            # ===== AUTO RENAME =====
            if auto_rename:
                new_name = f"gondezz_{int(time.time())}_{filename}"
                new_path = os.path.join(DOWNLOAD_FOLDER, new_name)
                if os.path.exists(filepath):
                    os.rename(filepath, new_path)
                    filename = new_name
                    filepath = new_path

            # ===== COMPRESS =====
            if is_compress and format_type == 'mp4':
                compressed_path = os.path.join(DOWNLOAD_FOLDER, f"compressed_{filename}")
                if compress_video(filepath, compressed_path):
                    os.remove(filepath)
                    os.rename(compressed_path, filepath)

            # ===== CONVERT TO GIF =====
            if is_gif and format_type == 'mp4':
                gif_filename = f"{title}.gif"
                gif_path = os.path.join(DOWNLOAD_FOLDER, gif_filename)
                if convert_to_gif(filepath, gif_path):
                    os.remove(filepath)
                    filename = gif_filename
                    filepath = gif_path

            # ===== TRIM =====
            if trim_start and trim_end and format_type == 'mp4':
                trimmed_path = os.path.join(DOWNLOAD_FOLDER, f"trimmed_{filename}")
                if trim_video(filepath, trimmed_path, trim_start, trim_end):
                    os.remove(filepath)
                    os.rename(trimmed_path, filepath)

            if os.path.exists(filepath):
                size = get_file_size(filepath)
                save_history(url, filename, platform, format_type, resolution, size)
                
                # Notifikasi (via file)
                if settings.get('notifications', True):
                    with open('notification.txt', 'w') as f:
                        f.write(f"✅ Download selesai: {filename}")
                
                return jsonify({
                    'status': 'success',
                    'filename': filename,
                    'platform': platform,
                    'size': size,
                    'message': f'Download berhasil! ({size})'
                })
            else:
                files = os.listdir(DOWNLOAD_FOLDER)
                if files:
                    size = get_file_size(os.path.join(DOWNLOAD_FOLDER, files[0]))
                    save_history(url, files[0], platform, format_type, resolution, size)
                    return jsonify({
                        'status': 'success',
                        'filename': files[0],
                        'platform': platform,
                        'size': size,
                        'message': f'Download berhasil! ({size})'
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

@app.route('/list-files')
def list_files():
    files = os.listdir(DOWNLOAD_FOLDER)
    result = []
    for f in files:
        path = os.path.join(DOWNLOAD_FOLDER, f)
        if os.path.isfile(path):
            result.append({
                'name': f,
                'size': get_file_size(path),
                'date': datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S')
            })
    return jsonify(result)

@app.route('/delete-file/<filename>', methods=['DELETE'])
def delete_file(filename):
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'File tidak ditemukan'}), 404

@app.route('/share/<filename>')
def share_file(filename):
    # Untuk sharing via intent
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({'status': 'error'}), 404

@app.route('/notification')
def get_notification():
    if os.path.exists('notification.txt'):
        with open('notification.txt', 'r') as f:
            content = f.read()
        os.remove('notification.txt')
        return jsonify({'message': content})
    return jsonify({'message': ''})

# ========== VOICE COMMAND (Simulasi) ==========
@app.route('/voice-command', methods=['POST'])
def voice_command():
    data = request.json
    command = data.get('command', '').lower()
    
    if 'download' in command:
        # Ekstrak URL dari command
        import re
        urls = re.findall(r'https?://[^\s]+', command)
        if urls:
            return jsonify({'action': 'download', 'url': urls[0]})
    return jsonify({'action': 'unknown'})

if __name__ == '__main__':
    print("🔥 GONDEZZ DOWNLOADER V2 — FULL 30 FITUR 🔥")
    print("🚀 Server berjalan di http://localhost:5000")
    print("📱 Buka di browser: http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
