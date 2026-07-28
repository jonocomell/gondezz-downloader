from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import yt_dlp
import os
import re
import time
import json
import subprocess
import base64
import random
import string
from datetime import datetime
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont, ImageFilter

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# ========== KONFIGURASI ==========
DOWNLOAD_FOLDER = "downloads"
HISTORY_FILE = "history.json"
UPLOAD_FOLDER = "uploads"
BRAT_FOLDER = "brat"
REMOVE_BG_FOLDER = "remove_bg"
FAKE_CALL_FOLDER = "fake_call"

for folder in [DOWNLOAD_FOLDER, UPLOAD_FOLDER, BRAT_FOLDER, REMOVE_BG_FOLDER, FAKE_CALL_FOLDER]:
    os.makedirs(folder, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'mp4', 'webm', 'mov'}

# ========== FUNGSI ==========
def sanitize_filename(filename):
    return re.sub(r'[^\w\s.-]', '', filename)

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

def save_history(url, filename, platform, format_type, resolution, size="0 MB"):
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            try:
                history = json.load(f)
            except:
                history = []
    history.append({
        'url': url, 'filename': filename, 'platform': platform,
        'format': format_type, 'resolution': resolution, 'size': size,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
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
    elif 'pinterest.com' in url:
        return 'Pinterest'
    else:
        return 'Unknown'

def convert_to_gif(input_path, output_path):
    try:
        cmd = ['ffmpeg', '-i', input_path, '-vf', 'fps=10,scale=320:-1:flags=lanczos', '-c:v', 'gif', '-loop', '0', output_path]
        subprocess.run(cmd, capture_output=True, text=True)
        return os.path.exists(output_path)
    except:
        return False

# ========== GENERATE FAKE CALL (Seperti Gambar) ==========
def generate_fake_call(name, output_path):
    try:
        # Ukuran gambar: 400x800 (seperti layar HP)
        img = Image.new('RGB', (400, 800), color='#0a0a1a')
        d = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 18)
            font_bold = ImageFont.truetype("arialbd.ttf", 22)
            font_small = ImageFont.truetype("arial.ttf", 14)
        except:
            font = ImageFont.load_default()
            font_bold = font
            font_small = font
        
        # Header - Background hijau WhatsApp
        d.rectangle([0, 0, 400, 70], fill='#075e54')
        
        # Tombol back
        d.text((15, 25), "‹", fill=(255, 255, 255), font=font_bold)
        
        # Judul header
        d.text((45, 28), "Panggilan", fill=(255, 255, 255), font=font)
        
        # Tombol lainnya
        d.text((360, 28), "⋯", fill=(255, 255, 255), font=font_bold)
        
        # Garis bawah header
        d.rectangle([0, 68, 400, 70], fill='#065a4d')
        
        # ===== PROFIL =====
        # Lingkaran profil besar
        circle_x = 200
        circle_y = 180
        radius = 80
        
        # Shadow
        d.ellipse([circle_x - radius - 5, circle_y - radius - 5, 
                   circle_x + radius + 5, circle_y + radius + 5], 
                  fill='#1a1a2e')
        
        # Lingkaran profil dengan gradien
        d.ellipse([circle_x - radius, circle_y - radius, 
                   circle_x + radius, circle_y + radius], 
                  fill='#6c2bd9')
        
        # Icon orang di tengah lingkaran
        # Kepala
        d.ellipse([185, 155, 215, 185], fill=(255, 255, 255, 80))
        # Badan
        d.ellipse([175, 195, 225, 215], fill=(255, 255, 255, 80))
        # Bahu
        d.ellipse([165, 210, 235, 235], fill=(255, 255, 255, 80))
        
        # ===== NAMA =====
        name_text = name if name else "Dek Piraa"
        # Bayangan nama
        d.text((200 - len(name_text) * 6, 285), name_text, fill=(150, 150, 150), font=font_bold)
        # Nama utama
        d.text((200 - len(name_text) * 6 - 1, 284), name_text, fill=(255, 255, 255), font=font_bold)
        
        # ===== STATUS "Berdering ..." =====
        status_text = "Berdering ..."
        d.text((200 - len(status_text) * 4, 318), status_text, fill=(150, 150, 150), font=font_small)
        
        # ===== IKON SPEAKER =====
        # Tombol Speaker (atas)
        d.ellipse([330, 360, 380, 410], fill='#1a1a2e', outline='#333', width=1)
        d.text((345, 378), "🔊", fill=(255, 255, 255), font=font_bold)
        d.text((340, 415), "Speaker", fill=(150, 150, 150), font=font_small)
        
        # ===== TOMBOL ANSWER (HIJAU) =====
        answer_x = 200
        answer_y = 520
        answer_r = 45
        
        # Shadow
        d.ellipse([answer_x - answer_r - 3, answer_y - answer_r - 3,
                   answer_x + answer_r + 3, answer_y + answer_r + 3],
                  fill='#1a3a1a')
        
        # Tombol Answer
        d.ellipse([answer_x - answer_r, answer_y - answer_r,
                   answer_x + answer_r, answer_y + answer_r],
                  fill='#25D366')
        
        # Icon telpon di dalam tombol
        d.text((answer_x - 12, answer_y - 10), "📞", fill=(255, 255, 255), font=font_bold)
        
        # Label Answer
        d.text((answer_x - 25, answer_y + 55), "Answer", fill=(150, 150, 150), font=font_small)
        
        # ===== TOMBOL DECLINE (MERAH) =====
        decline_x = 200
        decline_y = 620
        decline_r = 45
        
        # Shadow
        d.ellipse([decline_x - decline_r - 3, decline_y - decline_r - 3,
                   decline_x + decline_r + 3, decline_y + decline_r + 3],
                  fill='#3a1a1a')
        
        # Tombol Decline
        d.ellipse([decline_x - decline_r, decline_y - decline_r,
                   decline_x + decline_r, decline_y + decline_r],
                  fill='#ff2d55')
        
        # Icon X di dalam tombol
        d.text((decline_x - 10, decline_y - 10), "✕", fill=(255, 255, 255), font=font_bold)
        
        # Label Decline
        d.text((decline_x - 25, decline_y + 55), "Decline", fill=(150, 150, 150), font=font_small)
        
        # ===== TOMBOL MESSAGE (BAWAH) =====
        msg_x = 200
        msg_y = 710
        msg_r = 30
        
        d.ellipse([msg_x - msg_r, msg_y - msg_r,
                   msg_x + msg_r, msg_y + msg_r],
                  fill='#1a1a2e', outline='#333', width=1)
        d.text((msg_x - 10, msg_y - 8), "💬", fill=(255, 255, 255), font=font)
        
        # Label Message
        d.text((msg_x - 25, msg_y + 38), "Message", fill=(150, 150, 150), font=font_small)
        
        img.save(output_path)
        return True
    except Exception as e:
        print(f"Fake Call Error: {e}")
        return False

# ========== GENERATE BRAT ==========
def generate_brat_image(text, bg_color, output_path):
    try:
        img = Image.new('RGB', (500, 200), color=bg_color)
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 32)
        except:
            font = ImageFont.load_default()
        
        d.rectangle([5, 5, 495, 195], outline='white', width=3)
        d.text((15, 80), text, fill=(255, 255, 255), font=font)
        img.save(output_path)
        return True
    except Exception as e:
        print(f"BRAT Error: {e}")
        return False

# ========== ROUTES ==========
@app.route('/')
def index():
    return send_from_directory('.', 'indexV1.0.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)

@app.route('/history')
def history():
    return jsonify(load_history())

@app.route('/clear-history', methods=['POST'])
def clear_history():
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    return jsonify({'status': 'success'})

@app.route('/list-files')
def list_files():
    files = os.listdir(DOWNLOAD_FOLDER)
    result = []
    for f in files:
        path = os.path.join(DOWNLOAD_FOLDER, f)
        if os.path.isfile(path):
            result.append({'name': f, 'size': get_file_size(path), 'date': datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S')})
    return jsonify(result)

@app.route('/delete-file/<filename>', methods=['DELETE'])
def delete_file(filename):
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'File tidak ditemukan'}), 404

# ========== DOWNLOAD ==========
@app.route('/download', methods=['POST'])
def download():
    data = request.json
    url = data.get('url')
    format_type = data.get('format', 'mp4')
    resolution = data.get('resolution', 'HD')
    is_gif = data.get('gif', False)
    platform = data.get('platform', '')

    if not url:
        return jsonify({'status': 'error', 'message': 'URL tidak boleh kosong'}), 400

    try:
        for f in os.listdir(DOWNLOAD_FOLDER):
            file_path = os.path.join(DOWNLOAD_FOLDER, f)
            if os.path.isfile(file_path):
                os.remove(file_path)

        detected_platform = detect_platform(url) or platform
        ydl_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
            'quiet': True, 'no_warnings': True, 'ignoreerrors': True, 'extract_flat': False,
        }

        # ===== FORMAT UNTUK JPG/PNG =====
        if format_type in ['jpg', 'png']:
            ydl_opts['format'] = 'best[ext=webp]/best[ext=jpg]/best[ext=png]/best'
            ydl_opts['outtmpl'] = f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s'
        elif format_type == 'mp3':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
        else:
            res_map = {
                'Normal': 'bestvideo[height<=480]+bestaudio/best[height<=480]',
                'HD': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
                'ULTRA HD': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
                '2K': 'bestvideo[height<=1440]+bestaudio/best[height<=1440]'
            }
            ydl_opts['format'] = res_map.get(resolution, 'bestvideo[height<=720]+bestaudio/best[height<=720]')

        if detected_platform in ['Instagram', 'Pinterest']:
            ydl_opts['format'] = 'best'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                return jsonify({'status': 'error', 'message': 'Gagal mengekstrak data. Coba link langsung.'}), 400

            title = sanitize_filename(info.get('title', 'video'))
            
            if format_type in ['jpg', 'png']:
                ext = format_type
            elif format_type == 'mp3':
                ext = 'mp3'
            else:
                ext = 'mp4'
            
            filename = f"{title}.{ext}"
            filepath = os.path.join(DOWNLOAD_FOLDER, filename)

            new_name = f"Gondezz Downloader_{int(time.time())}_{filename}"
            new_path = os.path.join(DOWNLOAD_FOLDER, new_name)
            if os.path.exists(filepath):
                os.rename(filepath, new_path)
                filename = new_name
                filepath = new_path

            if is_gif and ext == 'mp4':
                gif_filename = f"{title}.gif"
                gif_path = os.path.join(DOWNLOAD_FOLDER, gif_filename)
                if convert_to_gif(filepath, gif_path):
                    os.remove(filepath)
                    filename = gif_filename
                    filepath = gif_path

            if os.path.exists(filepath):
                size = get_file_size(filepath)
                save_history(url, filename, detected_platform, format_type, resolution, size)
                return jsonify({'status': 'success', 'filename': filename, 'platform': detected_platform, 'size': size, 'message': f'Download berhasil! ({size})'})
            else:
                files = os.listdir(DOWNLOAD_FOLDER)
                if files:
                    size = get_file_size(os.path.join(DOWNLOAD_FOLDER, files[0]))
                    save_history(url, files[0], detected_platform, format_type, resolution, size)
                    return jsonify({'status': 'success', 'filename': files[0], 'platform': detected_platform, 'size': size, 'message': f'Download berhasil! ({size})'})
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

# ========== UPLOAD ==========
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Tidak ada file'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'File tidak dipilih'}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    return jsonify({
        'status': 'success',
        'filename': filename,
        'path': f'/uploads/{filename}',
        'message': 'File berhasil diupload'
    })

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ========== BRAT GENERATE ==========
@app.route('/brat-generate', methods=['POST'])
def brat_generate():
    data = request.json
    text = data.get('text', 'BRAT')
    bg_color = data.get('color', '#000000')
    filename = f"brat_{int(time.time())}.png"
    filepath = os.path.join(BRAT_FOLDER, filename)
    generate_brat_image(text, bg_color, filepath)
    return jsonify({'status': 'success', 'text': text, 'filename': filename, 'path': f'/brat/{filename}'})

@app.route('/brat/<filename>')
def brat_file(filename):
    return send_from_directory(BRAT_FOLDER, filename)

# ========== REMOVE BG ==========
@app.route('/remove-bg', methods=['POST'])
def remove_bg():
    data = request.json
    filename = data.get('filename', '')
    if not filename:
        return jsonify({'status': 'error', 'message': 'No file'}), 400
    
    input_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(input_path):
        return jsonify({'status': 'error', 'message': 'File not found'}), 404
    
    output_filename = f"removed_{filename}.png"
    output_path = os.path.join(REMOVE_BG_FOLDER, output_filename)
    
    try:
        img = Image.open(input_path).convert('RGBA')
        data_img = img.getdata()
        new_data = []
        for item in data_img:
            if item[0] > 200 and item[1] > 200 and item[2] > 200:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        img.putdata(new_data)
        img.save(output_path, 'PNG')
        return jsonify({
            'status': 'success',
            'message': 'Background berhasil dihapus!',
            'filename': output_filename,
            'path': f'/remove-bg/{output_filename}'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/remove-bg/<filename>')
def remove_bg_file(filename):
    return send_from_directory(REMOVE_BG_FOLDER, filename)

# ========== FAKE CALL ==========
@app.route('/fake-call', methods=['POST'])
def fake_call():
    data = request.json
    name = data.get('name', 'Dek Piraa')
    filename = f"fake_call_{int(time.time())}.png"
    filepath = os.path.join(FAKE_CALL_FOLDER, filename)
    generate_fake_call(name, filepath)
    return jsonify({'status': 'success', 'name': name, 'filename': filename, 'path': f'/fake-call/{filename}'})

@app.route('/fake-call/<filename>')
def fake_call_file(filename):
    return send_from_directory(FAKE_CALL_FOLDER, filename)

if __name__ == '__main__':
    print("🔥 GONDEZZ DOWNLOADER V1.0")
    print("🚀 Server: http://localhost:5000")
    print("📱 Buka di browser HP: http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
