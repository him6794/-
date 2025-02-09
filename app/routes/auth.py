from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, login_manager
from app.models import User  # 請確保 User 模型正確定義
# 將 found.py 的方法直接引入，確保 found.py 已包含這些方法的實作
from app.found import (
    register_user,
    login_user as found_login_user,
    get_trending_songs,
    get_songs,
    similarity_search
)
from sqlalchemy import text

bp = Blueprint('auth', __name__, url_prefix='/auth')

@login_manager.user_loader
def load_user(user_id):
    # 根據使用者主鍵（user_id）取得用戶資料
    return User.query.get(int(user_id))


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # 使用 found.py 的登入驗證邏輯
        result = found_login_user(username, password)
        if result['status'] == 'success':
            user = User.query.filter_by(username=username).first()
            if user:
                login_user(user)
                flash('登入成功', 'success')
                return redirect(url_for('auth.found'))
            else:
                flash('登入失敗，請檢查帳號或密碼', 'danger')
        else:
            flash(result['message'], 'danger')

    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('已登出', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # 採用 found.py 中的註冊方法
        result = register_user(username, password)
        if result['status'] == 'success':
            flash('註冊成功！請登入。', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(result['message'], 'danger')

    return render_template('register.html')


@bp.route('/found', methods=['GET', 'POST'])
@login_required
def found():
    results = []
    top_songs = get_trending_songs(limit=10)

    # 获取用户歌单
    with db.engine.connect() as conn:
        result = conn.execute(
            text("SELECT playlist_id, name FROM playlists WHERE user_id = :user_id"),
            {"user_id": current_user.user_id}
        )
        playlists = [dict(row._mapping) for row in result]

    if request.method == 'POST':
        # 获取所有表单参数
        song_title = request.form.get('song_title')
        author = request.form.get('author')
        category = request.form.get('category')
        music_key = request.form.get('music_key')
        tempo_start = request.form.get('tempo_start')
        tempo_end = request.form.get('tempo_end')
        lyrics = request.form.get('lyrics')

        # 处理节奏范围
        try:
            tempo_start = int(tempo_start) if tempo_start else None
            tempo_end = int(tempo_end) if tempo_end else None
        except ValueError:
            tempo_start = tempo_end = None

        # 执行主搜索
        results = get_songs(
            search_term=song_title,
            author=author,
            category=category,
            music_key=music_key,
            min_tempo=tempo_start,
            max_tempo=tempo_end,
            limit=20
        )

        # 附加歌词相似度搜索
        if lyrics:
            lyrics_results = similarity_search(lyrics, limit=5)
            # 合并结果并去重
            seen_uuids = {s['uuid'] for s in results}
            for song in lyrics_results:
                if song['uuid'] not in seen_uuids:
                    results.append(song)
                    seen_uuids.add(song['uuid'])

    return render_template('found.html', 
                         results=results, 
                         top_songs=top_songs, 
                         playlists=playlists)
    # 將搜尋結果、熱門歌曲及歌單傳遞給模板