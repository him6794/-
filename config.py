# create_tables.py
from app import create_app, db

app = create_app()

with app.app_context():
    # 創建默認數據庫表
    db.create_all()
    
    # 創建 music 數據庫表
    db.create_all(bind='music')
    
    print("數據庫初始化完成！")