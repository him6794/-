from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import uuid
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

DB_PATH = r"D:\vscode\project\instance\music_library.db"
UPLOAD_FOLDER = r"D:\vscode\project\檔案"

# 確保上傳資料夾存在，否則創建
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# 創建歌曲接口（文件上傳後自動生成路徑）
@app.route('/create_song', methods=['GET', 'POST'])
def create_song():
    if request.method == 'POST':
        # 表單文字欄位
        song_title = request.form['song_title']
        tags = request.form['tags']
        music_key = request.form['music_key']
        author = request.form['author']
        lyrics = request.form['lyrics']
        category = request.form['category']
        tempo_start = request.form['tempo_start']
        tempo_end = request.form['tempo_end']
        source = request.form['source']

        # 處理文件上傳：文件、封面圖片、MP3文件
        # 1. 文件上傳
        file_upload = request.files.get('path')
        if file_upload and file_upload.filename != '':
            filename = secure_filename(file_upload.filename)
            new_filename = f"{uuid.uuid4()}_{filename}"
            file_path_full = os.path.join(UPLOAD_FOLDER, new_filename)
            file_upload.save(file_path_full)
        else:
            file_path_full = ''

        # 2. 封面圖片上傳
        img_file = request.files.get('img_url')
        if img_file and img_file.filename != '':
            filename = secure_filename(img_file.filename)
            new_filename = f"{uuid.uuid4()}_{filename}"
            img_path_full = os.path.join(UPLOAD_FOLDER, new_filename)
            img_file.save(img_path_full)
        else:
            img_path_full = ''

        # 3. MP3 文件上傳
        mp3_file = request.files.get('mp3_url')
        if mp3_file and mp3_file.filename != '':
            filename = secure_filename(mp3_file.filename)
            new_filename = f"{uuid.uuid4()}_{filename}"
            mp3_path_full = os.path.join(UPLOAD_FOLDER, new_filename)
            mp3_file.save(mp3_path_full)
        else:
            mp3_path_full = ''

        song_uuid = str(uuid.uuid4())

        # 將數據存入資料庫
        conn = db_connection()
        conn.execute("""
            INSERT INTO songs (uuid, song_title, tags, music_key, author, lyrics, category, tempo_start, tempo_end, source, path, img_url, mp3_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (song_uuid, song_title, tags, music_key, author, lyrics, category, tempo_start, tempo_end, source, file_path_full, img_path_full, mp3_path_full))
        conn.commit()

        return redirect(url_for('song_list'))
    
    return render_template('create_song.html')

# 歌曲列表頁面
@app.route('/songs')
def song_list():
    conn = db_connection()
    songs = conn.execute("SELECT * FROM songs").fetchall()
    return render_template('song_list.html', songs=songs)

# 編輯歌曲接口（支持更新文件上傳，如未上傳則保留原路徑）
@app.route('/edit_song/<uuid>', methods=['GET', 'POST'])
def edit_song(uuid):
    conn = db_connection()
    song = conn.execute("SELECT * FROM songs WHERE uuid = ?", (uuid,)).fetchone()
    if request.method == 'POST':
        song_title = request.form['song_title']
        tags = request.form['tags']
        music_key = request.form['music_key']
        author = request.form['author']
        lyrics = request.form['lyrics']
        category = request.form['category']
        tempo_start = request.form['tempo_start']
        tempo_end = request.form['tempo_end']
        source = request.form['source']

        # 文件上傳處理：若有新文件則更新，否則使用隱藏欄位中的原始路徑
        file_upload = request.files.get('path')
        if file_upload and file_upload.filename != '':
            filename = secure_filename(file_upload.filename)
            new_filename = f"{uuid.uuid4()}_{filename}"
            file_path_full = os.path.join(UPLOAD_FOLDER, new_filename)
            file_upload.save(file_path_full)
        else:
            file_path_full = request.form.get('existing_path', song['path'])

        # 封面圖片更新
        img_file = request.files.get('img_url')
        if img_file and img_file.filename != '':
            filename = secure_filename(img_file.filename)
            new_filename = f"{uuid.uuid4()}_{filename}"
            img_path_full = os.path.join(UPLOAD_FOLDER, new_filename)
            img_file.save(img_path_full)
        else:
            img_path_full = request.form.get('existing_img_url', song['img_url'])

        # MP3 文件更新
        mp3_file = request.files.get('mp3_url')
        if mp3_file and mp3_file.filename != '':
            filename = secure_filename(mp3_file.filename)
            new_filename = f"{uuid.uuid4()}_{filename}"
            mp3_path_full = os.path.join(UPLOAD_FOLDER, new_filename)
            mp3_file.save(mp3_path_full)
        else:
            mp3_path_full = request.form.get('existing_mp3_url', song['mp3_url'])

        conn.execute("""
            UPDATE songs
            SET song_title = ?, tags = ?, music_key = ?, author = ?, lyrics = ?, category = ?, tempo_start = ?, tempo_end = ?, source = ?, path = ?, img_url = ?, mp3_url = ?
            WHERE uuid = ?
        """, (song_title, tags, music_key, author, lyrics, category, tempo_start, tempo_end, source, file_path_full, img_path_full, mp3_path_full, uuid))
        conn.commit()
        
        return redirect(url_for('song_list'))
    
    return render_template('edit_song.html', song=song)

if __name__ == '__main__':
    app.run(debug=True)
