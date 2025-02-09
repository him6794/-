from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required, current_user
import os
import zipfile
import io
from app import found  # 直接导入 found 模块

bp = Blueprint('playlist', __name__, url_prefix='/playlist')

@bp.route('/')
@login_required
def list_playlists():
    """显示用户的所有歌单"""
    with found.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.playlist_id, p.name, p.created_at,
                   COUNT(ps.song_uuid) as song_count
            FROM playlists p
            LEFT JOIN playlist_songs ps ON p.playlist_id = ps.playlist_id
            WHERE p.user_id = ?
            GROUP BY p.playlist_id
            ORDER BY p.created_at DESC
        """, (current_user.user_id,))  # 使用 user_id 而非 id
        playlists = [dict(row) for row in cursor.fetchall()]
    return render_template('list.html', playlists=playlists)

@bp.route('/create', methods=['POST'])
@login_required
def create_playlist():
    """创建新歌单（完全使用 found.py 的函数）"""
    name = request.json.get('name')
    if not name:
        return jsonify({'success': False, 'message': '歌单名称不能为空'}), 400

    # 调用 found.py 的创建歌单函数
    result = found.create_playlist(
        user_id=current_user.user_id,  # 修改为 user_id
        name=name
    )

    if result['status'] == 'success':
        # 获取完整歌单信息
        with found.db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.playlist_id, p.name, p.created_at, 
                       COUNT(ps.song_uuid) as song_count 
                FROM playlists p
                LEFT JOIN playlist_songs ps ON p.playlist_id = ps.playlist_id
                WHERE p.playlist_id = ?
            """, (result['playlist_id'],))
            new_playlist = dict(cursor.fetchone())
        return jsonify({
            'success': True,
            'message': '歌单创建成功',
            'playlist': new_playlist
        })
    else:
        return jsonify({
            'success': False,
            'message': result['message']
        }), 400

@bp.route('/<int:playlist_id>/add_song', methods=['POST'])
@login_required
def add_song(playlist_id):
    """添加歌曲到歌单（使用 found.py 的批量管理函数）"""
    song_uuid = request.json.get('song_uuid')
    print(f"接收到的 song_uuid: {song_uuid}")  # 輸出 song_uuid

    if not song_uuid:
        return jsonify({'success': False, 'message': '未指定歌曲'}), 400

    # 权限验证：确保该歌单属于当前用户
    with found.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT playlist_id FROM playlists 
            WHERE playlist_id = ? AND user_id = ? 
        """, (playlist_id, current_user.user_id))
        if not cursor.fetchone():
            return jsonify({'success': False, 'message': '无权限操作'}), 403

    # 调用 found.py 的歌曲管理函数
    result = found.manage_playlist_songs(
        playlist_id=playlist_id,
        song_uuids=[song_uuid],
        action='add'
    )

    print(f"歌曲添加结果: {result}")

    if result['status'] == 'success':
        return jsonify({
            'success': True,
            'message': '歌曲添加成功',
            'affected_rows': result.get('affected_rows', 0)
        })
    else:
        return jsonify({
            'success': False,
            'message': result['message']
        }), 400

@bp.route('/<int:playlist_id>/export')
@login_required
def export_playlist(playlist_id):
    """導出歌單（保留原始資料夾結構）"""
    # 驗證歌單所有權
    with found.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM playlists 
            WHERE playlist_id = ? AND user_id = ?
        """, (playlist_id, current_user.user_id))
        playlist = cursor.fetchone()
        if not playlist:
            flash('歌單不存在或無權訪問', 'danger')
            return redirect(url_for('playlist.list_playlists'))
    playlist_name = playlist['name']

    # 獲取歌單歌曲
    songs = found.get_songs(playlist_id=playlist_id, limit=None)
    if not songs:
        flash('歌單中沒有歌曲', 'warning')
        return redirect(url_for('playlist.view_playlist', playlist_id=playlist_id))

    # 創建 ZIP 文件（在內存中生成）
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for song in songs:
            file_path = song.get('path')
            print(song.get('path'))
            
            if file_path and os.path.exists(file_path):
                # 將文件放入以歌單名稱命名的資料夾中
                file_name = os.path.basename(file_path)
                arcname = os.path.join(playlist_name, file_name)
                zf.write(file_path, arcname=arcname)
                
    memory_file.seek(0)
    return send_file(memory_file, download_name=f"{playlist_name}.zip", as_attachment=True)


@bp.route('/<int:playlist_id>/remove_song', methods=['POST'])
@login_required
def remove_song(playlist_id):
    """从歌单移除歌曲（使用 found.py 的函数）"""
    song_uuid = request.json.get('song_uuid')
    if not song_uuid:
        return jsonify({'success': False, 'message': '未指定歌曲'}), 400

    result = found.manage_playlist_songs(
        playlist_id=playlist_id,
        song_uuids=[song_uuid],
        action='remove'
    )

    if result['status'] == 'success':
        return jsonify({'success': True, 'message': '歌曲已移除'})
    else:
        return jsonify({'success': False, 'message': result['message']}), 400

@bp.route('/<int:playlist_id>')
@login_required
def view_playlist(playlist_id):
    """查看歌單詳細頁"""
    with found.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.playlist_id, p.name, p.created_at,
                   COUNT(ps.song_uuid) as song_count
            FROM playlists p
            LEFT JOIN playlist_songs ps ON p.playlist_id = ps.playlist_id
            WHERE p.playlist_id = ? AND p.user_id = ?
            GROUP BY p.playlist_id
        """, (playlist_id, current_user.user_id))
        playlist = cursor.fetchone()

    if not playlist:
        flash('歌單不存在或無權訪問', 'danger')
        return redirect(url_for('playlist.list_playlists'))

    # 查詢歌曲列表
    with found.db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*
            FROM songs s
            JOIN playlist_songs ps ON s.uuid = ps.song_uuid
            WHERE ps.playlist_id = ?
        """, (playlist_id,))
        songs = cursor.fetchall()

    return render_template('view.html', playlist=playlist, songs=songs)
