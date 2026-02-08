from flask import render_template, request, redirect, url_for, session, flash, send_from_directory
import hashlib
import os
from functools import wraps
from app.main import main_bp
from app.utils.db import DatabaseConnection

# 配置
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# 登录装饰器
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('main.login'))
            if role and session.get('role') != role:
                flash('权限不足')
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 登录页面
@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        name = request.form['name']
        class_id = request.form['class_id']
        credential = request.form['credential']
        
        # 管理员登录
        if class_id == '000' and name == ADMIN_USERNAME and credential == ADMIN_PASSWORD:
            session['user_id'] = 0
            session['name'] = name
            session['role'] = 'admin'
            return redirect(url_for('admin.dashboard'))
        
        # 教师和学生登录
        with DatabaseConnection() as c:
            # 教师登录
            c.execute("SELECT * FROM users WHERE name = ? AND class_id = ? AND password = ? AND role = 'teacher'", (name, class_id, hash_password(credential)))
            teacher = c.fetchone()
            if teacher:
                session['user_id'] = teacher[0]
                session['name'] = teacher[1]
                session['role'] = 'teacher'
                session['class_id'] = teacher[2]
                return redirect(url_for('teacher.dashboard'))
            
            # 学生登录
            c.execute("SELECT * FROM users WHERE name = ? AND class_id = ? AND id_card_last8 = ? AND role = 'student'", (name, class_id, credential))
            student = c.fetchone()
            if student:
                session['user_id'] = student[0]
                session['name'] = student[1]
                session['role'] = 'student'
                session['class_id'] = student[2]
                session['group_id'] = student[3]
                return redirect(url_for('student.dashboard'))
        
        flash('登录失败，请检查输入信息')
    return render_template('login.html')

# 退出登录
@main_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.login'))

# 首页
@main_bp.route('/')
def index():
    if 'user_id' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif session['role'] == 'teacher':
            return redirect(url_for('teacher.dashboard'))
        elif session['role'] == 'student':
            return redirect(url_for('student.dashboard'))
    return redirect(url_for('main.login'))

from flask import current_app

# 查看提交详情
@main_bp.route('/view_submission/<int:submission_id>')
def view_submission(submission_id):
    with DatabaseConnection() as c:
        c.execute("SELECT s.*, a.title, u.name, u.class_id, u.group_id, u.id_card_last8 FROM submissions s JOIN assignments a ON s.assignment_id = a.id JOIN users u ON s.student_id = u.id WHERE s.id = ?", (submission_id,))
        submission = c.fetchone()
        
        # 获取作业内容
        assignment_id = submission[1]
        c.execute("SELECT content FROM assignments WHERE id = ?", (assignment_id,))
        assignment = c.fetchone()
        assignment_content = assignment[0] if assignment else None
    
    # 读取文本文件内容
    content = ''
    if submission[4]:
        # 使用current_app获取应用配置中的UPLOAD_FOLDER
        upload_folder = current_app.config['UPLOAD_FOLDER']
        text_file_path = os.path.join(upload_folder, f"{submission[4]}.txt")
        try:
            # 使用上下文管理器确保文件正确关闭
            with open(text_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            # 记录错误但不影响用户体验
            print(f"读取文本文件错误: {e}")
            pass
    
    # 查找对应的图片文件
    image_file = None
    if submission[5]:
        # 使用current_app获取应用配置中的UPLOAD_FOLDER
        upload_folder = current_app.config['UPLOAD_FOLDER']
        # 查找所有可能的图片扩展名
        image_extensions = ['jpg', 'jpeg', 'png', 'gif']
        for ext in image_extensions:
            image_path = os.path.join(upload_folder, f"{submission[5]}.{ext}")
            if os.path.exists(image_path):
                image_file = f"{submission[5]}.{ext}"
                break
    
    return render_template('view_submission_detail.html', submission=submission, content=content, image_file=image_file, assignment_content=assignment_content)

# 静态文件服务
@main_bp.route('/uploads/<path:filename>')
def download_file(filename):
    # 防止路径遍历攻击
    safe_filename = os.path.basename(filename)
    # 使用current_app获取应用配置中的UPLOAD_FOLDER
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], safe_filename, as_attachment=False)

# 工具函数
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
