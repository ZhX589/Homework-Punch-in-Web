from flask import Flask
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# 配置
# 使用绝对路径，确保指向项目根目录的static/uploads文件夹
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_FOLDER = os.path.join(PROJECT_ROOT, '..', 'static')
UPLOAD_FOLDER = os.path.join(STATIC_FOLDER, 'uploads')
UPLOAD_FOLDER = os.path.normpath(UPLOAD_FOLDER)
# 确保static目录和uploads目录存在
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
print(f"UPLOAD_FOLDER配置为: {UPLOAD_FOLDER}")

# 导入蓝图
from app.admin import admin_bp
from app.teacher import teacher_bp
from app.student import student_bp
from app.main import main_bp

# 注册蓝图
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(teacher_bp, url_prefix='/teacher')
app.register_blueprint(student_bp, url_prefix='/student')
app.register_blueprint(main_bp, url_prefix='/')
