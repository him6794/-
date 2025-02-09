from app import app
from flask import Flask, redirect
#@app.errorhandler(404)
def page_not_found(e):
    #返回到登录页面
    return redirect("http://192.168.10.124:5555/auth/login")
if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0',port=5555)
