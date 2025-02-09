from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# 多對多關聯表（playlist 和 song）
playlist_song = db.Table('playlist_song',
    db.Column('playlist_id', db.Integer, db.ForeignKey('playlists.id'), primary_key=True),
    db.Column('song_id', db.Integer, db.ForeignKey('songs.id'), primary_key=True)  # 這裡不再用 `music.songs`
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)  # 這裡是 user_id，不是 id
    username = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    playlists = db.relationship('Playlist', backref='creator', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # **新增這個方法**
    def get_id(self):
        return str(self.user_id)  # 必須返回字串格式

class Playlist(db.Model):
    __tablename__ = 'playlists'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)  # 修正這裡！
    name = db.Column(db.String(255), nullable=False)
    


class Song(db.Model):
    __tablename__ = 'songs'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    artist = db.Column(db.String(128))
    category = db.Column(db.String(64))
    tempo = db.Column(db.Integer)
    lyrics = db.Column(db.Text)
    popularity = db.Column(db.Integer, default=0)  # 用於熱門歌曲排序
    path = db.Column(db.String(512), nullable=False)  # 加上歌曲文件路徑
    tags = db.Column(db.String(256))  # 讓它支持標籤

from app import db
from app.models import Song

def get_trending_songs(limit=10):
    return Song.query.order_by(Song.popularity.desc()).limit(limit).all()
    