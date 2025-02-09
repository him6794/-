from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import uuid
from flask import Blueprint
bp = Blueprint('admin', __name__, url_prefix='/admin')

DB_PATH = r"D:\vscode\project\instance\music_library.db"

# 数据库连接
def db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# 歌曲創建接口
@bp.route('/')
@bp.route('/create_song', methods=['GET', 'POST'])
def create_song():
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
        path = request.form['path']
        img_url = request.form['img_url']
        mp3_url = request.form['mp3_url']
        
        song_uuid = str(uuid.uuid4())

        # 插入到数据库
        conn = db_connection()
        conn.execute("""
            INSERT INTO songs (uuid, song_title, tags, music_key, author, lyrics, category, tempo_start, tempo_end, source, path, img_url, mp3_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (song_uuid, song_title, tags, music_key, author, lyrics, category, tempo_start, tempo_end, source, path, img_url, mp3_url))
        conn.commit()
        
        return redirect(url_for('song_list'))
    
    return render_template('create_song.html')

# 歌曲列表頁面
@bp.route('/songs')
def song_list():
    conn = db_connection()
    songs = conn.execute("SELECT * FROM songs").fetchall()
    return render_template('song_list.html', songs=songs)

# 編輯歌曲頁面
@bp.route('/edit_song/<uuid>', methods=['GET', 'POST'])
def edit_song(uuid):
    conn = db_connection()
    
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
        path = request.form['path']
        img_url = request.form['img_url']
        mp3_url = request.form['mp3_url']

        conn.execute("""
            UPDATE songs
            SET song_title = ?, tags = ?, music_key = ?, author = ?, lyrics = ?, category = ?, tempo_start = ?, tempo_end = ?, source = ?, path = ?, img_url = ?, mp3_url = ?
            WHERE uuid = ?
        """, (song_title, tags, music_key, author, lyrics, category, tempo_start, tempo_end, source, path, img_url, mp3_url, uuid))
        conn.commit()
        
        return redirect(url_for('song_list'))
    
    song = conn.execute("SELECT * FROM songs WHERE uuid = ?", (uuid,)).fetchone()
    return render_template('edit_song.html', song=song)
