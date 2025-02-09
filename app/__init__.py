from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

# 只創建一個 SQLAlchemy 物件
db = SQLAlchemy()
login_manager = LoginManager()

app = Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///music_library.db'  # 用戶 & 歌曲資料放在同一個 DB

app.config['SECRET_KEY'] = os.urandom(24)  # 生成一個隨機的 24 字節密鑰


# 只初始化一次 SQLAlchemy
db.init_app(app)
login_manager.init_app(app)

login_manager.login_view = 'auth.login'

# 註冊藍圖
from app.routes import auth, playlists
app.register_blueprint(auth.bp)
app.register_blueprint(playlists.bp)
