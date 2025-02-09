import sqlite3
from typing import Optional, List, Dict, Any, Generator
import os
import uuid
import hashlib
from contextlib import contextmanager
from difflib import SequenceMatcher

# 数据库路径（当第二个参数为绝对路径时，os.path.join会返回该绝对路径）
DB_PATH = os.path.join(os.path.dirname(__file__), r"D:\vscode\project\instance\music_library.db")

# ========================
# 安全增强模块
# ========================
class Security:
    @staticmethod
    def hash_password(password: str, salt: Optional[bytes] = None) -> str:
        """使用PBKDF2进行安全密码哈希，返回格式为：{hash}{salt}，各64字符"""
        if salt is None:
            salt = os.urandom(32)
        return hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        ).hex() + salt.hex()

    @staticmethod
    def verify_password(stored_hash: str, password: str) -> bool:
        """验证密码与存储哈希是否匹配"""
        try:
            hash_part = bytes.fromhex(stored_hash[:64])
            salt = bytes.fromhex(stored_hash[64:])
            new_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt,
                100000
            )
            return hash_part == new_hash
        except Exception:
            return False

# ========================
# 数据库连接管理 (增强版)
# ========================
@contextmanager
def db_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    建立支持外键与事务管理的数据库连接。
    退出时自动提交事务（若无异常），否则回滚。
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
    try:
        yield conn
        conn.commit()  # 自动提交事务
    except sqlite3.Error as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# ========================
# 用户管理系统 (增强安全)
# ========================
def register_user(username: str, password: str) -> Dict[str, str]:
    """安全用户注册接口"""
    with db_connection() as conn:
        try:
            password_hash = Security.hash_password(password)
            conn.execute("""
                INSERT INTO users (username, password_hash)
                VALUES (?, ?)
            """, (username, password_hash))
            # 上下文管理器退出时自动提交
            return {"status": "success", "message": "註冊成功"}
        except sqlite3.IntegrityError:
            return {"status": "error", "message": "用戶名已被使用"}

def login_user(username: str, password: str) -> Dict[str, str]:
    """安全用户登录接口"""
    with db_connection() as conn:
        cursor = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?",
            (username,)
        )
        row = cursor.fetchone()
        
        if row is None:
            return {"status": "error", "message": "用戶名或密碼錯誤"}
        
        password_hash = row["password_hash"]  # 使用字典風格存取
        
        if Security.verify_password(password_hash, password):
            return {"status": "success", "message": "登入成功"}
        
        return {"status": "error", "message": "用戶名或密碼錯誤"}


# ========================
# 数据库初始化 (优化结构)
# ========================
def initialize_database():
    with db_connection() as conn:
        cursor = conn.cursor()

        # 用户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 歌曲表（包含生成列、检查约束与默认值）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS songs (
                uuid TEXT PRIMARY KEY,
                song_title TEXT NOT NULL,
                tags TEXT,
                music_key TEXT,
                author TEXT,
                lyrics TEXT,
                category TEXT,
                tempo_start INTEGER CHECK(tempo_start <= tempo_end),
                tempo_end INTEGER CHECK(tempo_end >= tempo_start),
                tempo_range TEXT GENERATED ALWAYS AS (
                    CASE 
                        WHEN tempo_start = tempo_end THEN CAST(tempo_start AS TEXT)
                        ELSE CAST(tempo_start AS TEXT) || '-' || CAST(tempo_end AS TEXT)
                    END
                ) VIRTUAL,
                source TEXT,
                path TEXT NOT NULL,
                query_count INTEGER DEFAULT 0,
                img_url TEXT,
                mp3_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                full_text_search TEXT GENERATED ALWAYS AS (
                    song_title || ' ' || COALESCE(author, '') || ' ' || COALESCE(lyrics, '') || ' ' || COALESCE(tags, '')
                ) VIRTUAL
            )
        """)

        # 索引创建
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_songs_full_text 
            ON songs(full_text_search)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_songs_tempo 
            ON songs(tempo_start, tempo_end)
        """)

        # 歌单表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                playlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, name),
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlist_songs (
                playlist_id INTEGER,
                song_uuid TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (playlist_id, song_uuid),
                FOREIGN KEY (playlist_id) REFERENCES playlists(playlist_id) ON DELETE CASCADE,
                FOREIGN KEY (song_uuid) REFERENCES songs(uuid) ON DELETE CASCADE
            )
        """)

# ========================
# 辅助查询模块
# ========================
class SongSearch:
    @staticmethod
    def build_search_query(
        search_term: Optional[str] = None,
        min_tempo: Optional[int] = None,
        max_tempo: Optional[int] = None,
        category: Optional[str] = None,
        author: Optional[str] = None,
        music_key: Optional[str] = None
    ) -> tuple[str, list]:
        """动态构建搜索查询"""
        base_query = """
            SELECT *, 
                   (query_count * 0.3 + similarity * 0.7) AS relevance
            FROM (
                SELECT *,
                       {similarity_clause}
                FROM songs
                WHERE 1=1
                {conditions}
            )
            ORDER BY relevance DESC, query_count DESC
            LIMIT ?
        """

        params = []
        conditions = []
        similarity_clause = "0 AS similarity"

        # 处理搜索词
        if search_term:
            similarity_clause = """
                ((song_title LIKE ?) * 3 +
                 (lyrics LIKE ?) * 2 +
                 (author LIKE ?) * 1.5 +
                 (tags LIKE ?) * 1) AS similarity
            """
            search_pattern = f"%{search_term}%"
            params.extend([search_pattern] * 4)

        # 处理节奏范围
        if min_tempo is not None:
            conditions.append("tempo_end >= ?")
            params.append(min_tempo)
        if max_tempo is not None:
            conditions.append("tempo_start <= ?")
            params.append(max_tempo)

        # 处理其他字段
        if category:
            conditions.append("category = ?")
            params.append(category)
        if author:
            conditions.append("author = ?")
            params.append(author)
        if music_key:
            conditions.append("music_key = ?")
            params.append(music_key)

        # 组合条件
        conditions_str = ""
        if conditions:
            conditions_str = "AND " + " AND ".join(conditions)

        return base_query.format(
            similarity_clause=similarity_clause,
            conditions=conditions_str
        ), params

# ========================
# 核心服务逻辑
# ========================
def create_song(**song_data) -> str:
    """通用歌曲创建接口，必需字段：song_title、path"""
    required_fields = {'song_title', 'path'}
    if not required_fields.issubset(song_data.keys()):
        raise ValueError("Missing required fields: 必须包含 song_title 和 path")

    song_uuid = str(uuid.uuid4())
    fields = ['uuid'] + list(song_data.keys())
    values = [song_uuid] + list(song_data.values())

    with db_connection() as conn:
        conn.execute(
            f"""
            INSERT INTO songs ({', '.join(fields)})
            VALUES ({', '.join('?' for _ in values)})
            """,
            values
        )
    return song_uuid

def get_trending_songs(limit: int = 10) -> List[Dict[str, Any]]:
    """獲取熱門歌曲，按照查詢次數排序"""
    with db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM songs
            ORDER BY query_count DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

def get_songs(
    search_term: Optional[str] = None,
    min_tempo: Optional[int] = None,
    max_tempo: Optional[int] = None,
    category: Optional[str] = None,
    author: Optional[str] = None,
    music_key: Optional[str] = None,
    limit: Optional[int] = 20,
    playlist_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    if playlist_id is not None:
        # 从特定歌单中查询歌曲
        query = """
            SELECT s.* 
            FROM songs s
            JOIN playlist_songs ps ON s.uuid = ps.song_uuid
            WHERE ps.playlist_id = ?
            ORDER BY s.created_at DESC
        """
        params = [playlist_id]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        with db_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    else:
        # 通用搜索逻辑
        query_builder = SongSearch()
        query, params = query_builder.build_search_query(
            search_term=search_term,
            min_tempo=min_tempo,
            max_tempo=max_tempo,
            category=category,
            author=author,
            music_key=music_key
        )
        # 添加 limit 参数
        params.append(limit)
        with db_connection() as conn:
            cursor = conn.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]
            if results:
                uuids = [song['uuid'] for song in results]
                conn.executemany(
                    "UPDATE songs SET query_count = query_count + 1 WHERE uuid = ?",
                    [(uid,) for uid in uuids]
                )
        return results

def get_recommendations(song_uuid: str, limit: int = 5) -> List[Dict[str, Any]]:
    """基于歌曲特征的推荐系统，排除目标歌曲并根据匹配分数排序"""
    with db_connection() as conn:
        target = conn.execute("""
            SELECT category, music_key, tempo_start, tempo_end 
            FROM songs WHERE uuid = ?
        """, (song_uuid,)).fetchone()

        if not target:
            return []

        cursor = conn.execute("""
            SELECT *, 
                   ABS(tempo_start - ?) * 0.5 +
                   ABS(tempo_end - ?) * 0.5 AS score
            FROM songs
            WHERE uuid != ?
              AND (category = ? OR music_key = ?)
            ORDER BY score ASC
            LIMIT ?
        """, (
            target['tempo_start'], target['tempo_end'],
            song_uuid, target['category'], target['music_key'], limit
        ))
        return [dict(row) for row in cursor.fetchall()]

def batch_update_songs(updates: List[Dict[str, Any]]) -> int:
    """批量更新歌曲信息，返回成功更新的记录数"""
    updated_count = 0
    with db_connection() as conn:
        for data in updates:
            song_uuid = data.get('uuid')
            if not song_uuid:
                continue
            # 避免直接修改原始数据
            update_data = {k: v for k, v in data.items() if k != 'uuid'}
            if not update_data:
                continue
            set_clause = ", ".join(f"{k} = ?" for k in update_data)
            values = list(update_data.values()) + [song_uuid]
            try:
                conn.execute(
                    f"UPDATE songs SET {set_clause} WHERE uuid = ?",
                    values
                )
                updated_count += 1
            except sqlite3.Error:
                continue
    return updated_count

def similarity_search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """基于歌词相似度的深度搜索"""
    with db_connection() as conn:
        cursor = conn.execute("SELECT uuid, lyrics FROM songs WHERE lyrics IS NOT NULL")
        candidates = [dict(row) for row in cursor.fetchall()]

    # 使用 SequenceMatcher 计算相似度
    query_lower = query.lower()
    scored_songs = []
    for song in candidates:
        lyric = song['lyrics'].lower()
        matcher = SequenceMatcher(None, query_lower, lyric)
        score = matcher.ratio() * 0.8  # 主要相似度

        # 添加附加评分因素
        if query_lower in lyric:
            score += 0.15
        if lyric.startswith(query_lower):
            score += 0.05

        if score > 0.4:  # 设置最低阈值
            scored_songs.append((score, song['uuid']))

    # 选取得分最高的歌曲
    sorted_songs = sorted(scored_songs, key=lambda x: x[0], reverse=True)[:limit]
    uuids = [uid for _, uid in sorted_songs]
    if not uuids:
        return []

    # 根据排序后的 uuid 列表获取完整歌曲信息
    placeholders = ','.join('?' for _ in uuids)
    order_case = ' '.join(f'WHEN uuid = ? THEN {i}' for i, _ in enumerate(uuids))
    final_query = f"""
        SELECT * FROM songs 
        WHERE uuid IN ({placeholders})
        ORDER BY CASE {order_case} END
    """
    params = uuids + uuids  # 参数数量需与 CASE 子句匹配
    with db_connection() as conn:
        cursor = conn.execute(final_query, params)
        return [dict(row) for row in cursor.fetchall()]
    
# ========================
# 歌单管理系统
# ========================
def create_playlist(user_id: int, name: str) -> Dict[str, Any]:
    """创建新歌单（带数量限制检查）"""
    with db_connection() as conn:
        try:
            with conn:
                # 使用事务保证原子性
                conn.execute("""
                    INSERT INTO playlists (user_id, name)
                    SELECT ?, ?
                    WHERE (SELECT COUNT(*) FROM playlists WHERE user_id = ?) < 50
                """, (user_id, name, user_id))
                
                if conn.total_changes == 0:
                    return {"status": "error", "message": "歌单数量已达上限（50个）"}
                
                playlist_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                return {"status": "success", "playlist_id": playlist_id}
        except sqlite3.IntegrityError:
            return {"status": "error", "message": "歌单名称已存在"}

def manage_playlist_songs(playlist_id: int, song_uuids: List[str], action: str = 'add') -> Dict[str, Any]:
    """批量管理歌单歌曲（添加/删除）"""
    if action not in ('add', 'remove'):
        return {"status": "error", "message": "无效操作类型"}

    with db_connection() as conn:
        try:
            with conn:
                if action == 'add':
                    # 使用 INSERT OR IGNORE 避免重复添加
                    conn.executemany(
                        "INSERT OR IGNORE INTO playlist_songs (playlist_id, song_uuid) VALUES (?, ?)",
                        [(playlist_id, uid) for uid in song_uuids]
                    )
                else:
                    conn.executemany(
                        "DELETE FROM playlist_songs WHERE playlist_id = ? AND song_uuid = ?",
                        [(playlist_id, uid) for uid in song_uuids]
                    )
                return {"status": "success", "affected_rows": conn.total_changes}
        except sqlite3.Error as e:
            return {"status": "error", "message": f"数据库错误: {str(e)}"}

# ========================
# 测试与示例
# ========================
if __name__ == '__main__':
    initialize_database()
    
    # 测试用户系统
    print(register_user("admin", "SecurePass123!"))
    print(login_user("admin", "SecurePass123!"))
    
    # 测试歌曲创建
    demo_id = create_song(
        song_title="Bohemian Rhapsody",
        path="/queen",
        music_key="C#",
        author="Queen",
        category="Rock"
    )
    print(f"Created song with UUID: {demo_id}")
    
    # 测试推荐系统
    recommendations = get_recommendations(demo_id)
    print("Recommendations:", recommendations)
    
    # 测试批量更新
    batch_result = batch_update_songs([{
        'uuid': demo_id,
        'tempo_start': 72,
        'tempo_end': 84
    }])
    print("Batch update count:", batch_result)
    
    # 测试基于歌词的相似搜索
    sim_results = similarity_search("you can dance")
    print("Similarity search results:", sim_results)
