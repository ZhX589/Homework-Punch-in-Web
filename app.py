from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import sqlite3
import csv
import os
import uuid
import hashlib
from datetime import datetime
from functools import wraps

# 数据库连接上下文管理器
# 用于自动管理数据库连接的创建和关闭，确保资源正确释放
class DatabaseConnection:
    def __enter__(self):
        # 进入上下文时创建数据库连接
        self.conn = sqlite3.connect('todo_school.db')
        self.c = self.conn.cursor()
        return self.c
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 退出上下文时提交事务并关闭连接
        if exc_type is None:
            self.conn.commit()
        self.conn.close()

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# 配置文件
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'
# 使用绝对路径，确保不受工作目录影响
# 项目根目录是app.py所在目录的父目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 密码加密函数
def hash_password(password):
    # 使用更安全的哈希方式
    return hashlib.sha256(password.encode()).hexdigest()

# 允许的图片扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 初始化数据库
def init_db():
    conn = sqlite3.connect('todo_school.db')
    c = conn.cursor()
    
    # 用户表
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT NOT NULL,
                 class_id TEXT NOT NULL,
                 group_id INTEGER,
                 id_card_last8 TEXT,
                 password TEXT,
                 role TEXT NOT NULL,
                 is_group_leader INTEGER DEFAULT 0
             )''')
    
    # 作业表
    c.execute('''CREATE TABLE IF NOT EXISTS assignments (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 teacher_id INTEGER NOT NULL,
                 class_id TEXT NOT NULL,
                 title TEXT NOT NULL,
                 content TEXT,
                 file_path TEXT,
                 deadline DATE NOT NULL,
                 created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                 FOREIGN KEY (teacher_id) REFERENCES users (id)
             )''')
    
    # 作业提交表
    c.execute('''CREATE TABLE IF NOT EXISTS submissions (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 assignment_id INTEGER NOT NULL,
                 student_id INTEGER NOT NULL,
                 content TEXT,
                 file_path TEXT,
                 submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                 score TEXT,
                 scorer_id INTEGER,
                 FOREIGN KEY (assignment_id) REFERENCES assignments (id),
                 FOREIGN KEY (student_id) REFERENCES users (id),
                 FOREIGN KEY (scorer_id) REFERENCES users (id)
             )''')
    
    conn.commit()
    conn.close()

# 登录装饰器
# 用于验证用户是否登录，以及是否具有特定角色权限
# role参数：指定需要的角色，如'admin'、'teacher'、'student'，为None时只验证登录状态
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 检查是否登录
            if 'user_id' not in session:
                return redirect(url_for('login'))
            # 检查角色权限
            if role and session.get('role') != role:
                flash('权限不足')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 登录页面
@app.route('/login', methods=['GET', 'POST'])
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
            return redirect(url_for('admin_dashboard'))
        
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
                return redirect(url_for('teacher_dashboard'))
            
            # 学生登录
            c.execute("SELECT * FROM users WHERE name = ? AND class_id = ? AND id_card_last8 = ? AND role = 'student'", (name, class_id, credential))
            student = c.fetchone()
            if student:
                session['user_id'] = student[0]
                session['name'] = student[1]
                session['role'] = 'student'
                session['class_id'] = student[2]
                session['group_id'] = student[3]
                return redirect(url_for('student_dashboard'))
        
        flash('登录失败，请检查输入信息')
    return render_template('login.html')

# 退出登录
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 首页
@app.route('/')
def index():
    if 'user_id' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session['role'] == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        elif session['role'] == 'student':
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

# # 管理员后台
@app.route('/admin/dashboard')
@login_required('admin')
def admin_dashboard():
    with DatabaseConnection() as c:
        # 获取总学生数
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'student'")
        total_students = c.fetchone()[0]
        
        # 获取总作业数
        c.execute("SELECT COUNT(*) FROM assignments")
        total_assignments = c.fetchone()[0]
        
        # 获取总提交数
        c.execute("SELECT COUNT(*) FROM submissions")
        total_submissions = c.fetchone()[0]
        
        # 计算总提交率
        total_completion_rate = (total_submissions / (total_students * total_assignments) * 100) if total_students * total_assignments > 0 else 0
        
        # 获取今日日期
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 获取今日提交数
        c.execute("SELECT COUNT(*) FROM submissions WHERE DATE(submitted_at) = ?", (today,))
        today_submissions = c.fetchone()[0]
        
        # 获取今日应提交作业数（今日截止的作业数 * 学生数）
        c.execute("SELECT COUNT(*) FROM assignments WHERE deadline = ?", (today,))
        today_assignments = c.fetchone()[0]
        today_expected_submissions = today_assignments * total_students
        
        # 计算今日提交率
        today_completion_rate = (today_submissions / today_expected_submissions * 100) if today_expected_submissions > 0 else 0
    
    return render_template('admin_dashboard.html', 
                           total_students=total_students,
                           total_assignments=total_assignments,
                           total_submissions=total_submissions,
                           total_completion_rate=total_completion_rate,
                           today_submissions=today_submissions,
                           today_expected_submissions=today_expected_submissions,
                           today_completion_rate=today_completion_rate)

# 添加教师
@app.route('/admin/add_teacher', methods=['GET', 'POST'])
@login_required('admin')
def admin_add_teacher():
    if request.method == 'POST':
        name = request.form['name']
        class_id = request.form['class_id']
        password = request.form['password']
        
        with DatabaseConnection() as c:
            c.execute("INSERT INTO users (name, class_id, role, password) VALUES (?, ?, 'teacher', ?)", (name, class_id, hash_password(password)))
        
        flash('教师添加成功')
        return redirect(url_for('admin_dashboard'))
    return render_template('add_teacher.html')

# 添加学生
@app.route('/admin/add_student', methods=['GET', 'POST'])
@login_required('admin')
def admin_add_student():
    if request.method == 'POST':
        name = request.form['name']
        class_id = request.form['class_id']
        group_id = request.form['group_id']
        id_card_last8 = request.form['id_card_last8']
        
        with DatabaseConnection() as c:
            c.execute("INSERT INTO users (name, class_id, group_id, id_card_last8, role) VALUES (?, ?, ?, ?, 'student')", (name, class_id, group_id, id_card_last8))
        
        flash('学生添加成功')
        return redirect(url_for('admin_dashboard'))
    return render_template('add_student.html')

# 通过CSV添加学生
@app.route('/admin/import_students', methods=['GET', 'POST'])
@login_required('admin')
def admin_import_students():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('请选择文件')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('请选择文件')
            return redirect(request.url)
        
        if file:
            # 读取CSV文件
            csv_reader = csv.reader(file.stream.read().decode('utf-8').splitlines())
            
            with DatabaseConnection() as c:
                for row in csv_reader:
                    if len(row) >= 4:
                        name = row[0].strip()
                        class_id = row[1].strip()
                        group_id = row[2].strip()
                        id_card_last8 = row[3].strip()
                        
                        c.execute("INSERT INTO users (name, class_id, group_id, id_card_last8, role) VALUES (?, ?, ?, ?, 'student')", (name, class_id, group_id, id_card_last8))
            
            flash('学生导入成功')
            return redirect(url_for('admin_dashboard'))
    return render_template('import_students.html')

# 管理员查看所有学生
@app.route('/admin/view_students')
@login_required('admin')
def admin_view_students():
    with DatabaseConnection() as c:
        c.execute("SELECT * FROM users WHERE role = 'student' ORDER BY class_id, name, id_card_last8")
        students = c.fetchall()
    return render_template('admin_view_students.html', students=students)

# 管理员查看所有教师
@app.route('/admin/view_teachers')
@login_required('admin')
def admin_view_teachers():
    with DatabaseConnection() as c:
        c.execute("SELECT * FROM users WHERE role = 'teacher' ORDER BY class_id, name")
        teachers = c.fetchall()
    return render_template('admin_view_teachers.html', teachers=teachers)

# # 教师后台
@app.route('/teacher/dashboard')
@login_required('teacher')
def teacher_dashboard():
    with DatabaseConnection() as c:
        # 获取本班学生数
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'student' AND class_id = ?", (session['class_id'],))
        class_students = c.fetchone()[0]
        
        # 获取本班作业数
        c.execute("SELECT COUNT(*) FROM assignments WHERE class_id = ?", (session['class_id'],))
        class_assignments = c.fetchone()[0]
        
        # 获取本班提交数
        c.execute("SELECT COUNT(*) FROM submissions s JOIN assignments a ON s.assignment_id = a.id WHERE a.class_id = ?", (session['class_id'],))
        class_submissions = c.fetchone()[0]
        
        # 计算本班总提交率
        class_completion_rate = (class_submissions / (class_students * class_assignments) * 100) if class_students * class_assignments > 0 else 0
        
        # 获取今日日期
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 获取今日本班提交数
        c.execute("SELECT COUNT(*) FROM submissions s JOIN assignments a ON s.assignment_id = a.id WHERE a.class_id = ? AND DATE(s.submitted_at) = ?", (session['class_id'], today))
        today_class_submissions = c.fetchone()[0]
        
        # 获取今日本班应提交作业数（今日截止的作业数 * 本班学生数）
        c.execute("SELECT COUNT(*) FROM assignments WHERE class_id = ? AND deadline = ?", (session['class_id'], today))
        today_class_assignments = c.fetchone()[0]
        today_class_expected_submissions = today_class_assignments * class_students
        
        # 计算今日本班提交率
        today_class_completion_rate = (today_class_submissions / today_class_expected_submissions * 100) if today_class_expected_submissions > 0 else 0
    
    return render_template('teacher_dashboard.html', 
                           class_students=class_students,
                           class_assignments=class_assignments,
                           class_submissions=class_submissions,
                           class_completion_rate=class_completion_rate,
                           today_class_submissions=today_class_submissions,
                           today_class_expected_submissions=today_class_expected_submissions,
                           today_class_completion_rate=today_class_completion_rate)

# 教师添加学生
@app.route('/teacher/add_student', methods=['GET', 'POST'])
@login_required('teacher')
def teacher_add_student():
    if request.method == 'POST':
        name = request.form['name']
        class_id = session['class_id']
        group_id = request.form['group_id']
        id_card_last8 = request.form['id_card_last8']
        
        with DatabaseConnection() as c:
            c.execute("INSERT INTO users (name, class_id, group_id, id_card_last8, role) VALUES (?, ?, ?, ?, 'student')", (name, class_id, group_id, id_card_last8))
        
        flash('学生添加成功')
        return redirect(url_for('teacher_dashboard'))
    return render_template('teacher_add_student.html')

# 教师通过CSV添加学生
@app.route('/teacher/import_students', methods=['GET', 'POST'])
@login_required('teacher')
def teacher_import_students():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('请选择文件')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('请选择文件')
            return redirect(request.url)
        
        if file:
            # 读取CSV文件
            csv_reader = csv.reader(file.stream.read().decode('utf-8').splitlines())
            
            with DatabaseConnection() as c:
                for row in csv_reader:
                    if len(row) >= 4:
                        name = row[0].strip()
                        class_id = session['class_id']  # 使用教师自己的班级
                        group_id = row[2].strip()
                        id_card_last8 = row[3].strip()
                        
                        c.execute("INSERT INTO users (name, class_id, group_id, id_card_last8, role) VALUES (?, ?, ?, ?, 'student')", (name, class_id, group_id, id_card_last8))
            
            flash('学生导入成功')
            return redirect(url_for('teacher_dashboard'))
    return render_template('teacher_import_students.html')

# 教师查看本班学生
@app.route('/teacher/view_students')
@login_required('teacher')
def teacher_view_students():
    with DatabaseConnection() as c:
        c.execute("SELECT * FROM users WHERE role = 'student' AND class_id = ? ORDER BY class_id, name, id_card_last8", (session['class_id'],))
        students = c.fetchall()
    return render_template('teacher_view_students.html', students=students)

# 布置作业
@app.route('/teacher/assign_assignment', methods=['GET', 'POST'])
@login_required('teacher')
def teacher_assign_assignment():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        deadline = request.form['deadline']
        
        # 文件上传
        file_path = None
        if 'file' in request.files and request.files['file'].filename != '':
            file = request.files['file']
            if allowed_file(file.filename):
                # 生成随机文件名，避免路径遍历攻击
                filename = str(uuid.uuid4()) + '.' + file.filename.split('.')[-1]
                # 确保路径安全
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                # 规范化路径，防止路径遍历
                file_path = os.path.normpath(file_path)
                # 确保文件保存在指定目录内
                if not os.path.abspath(file_path).startswith(os.path.abspath(UPLOAD_FOLDER)):
                    flash('文件上传路径错误')
                    return redirect(url_for('teacher_dashboard'))
                file.save(file_path)
        
        with DatabaseConnection() as c:
            c.execute("INSERT INTO assignments (teacher_id, class_id, title, content, file_path, deadline) VALUES (?, ?, ?, ?, ?, ?)", 
                      (session['user_id'], session['class_id'], title, content, file_path, deadline))
        
        flash('作业布置成功')
        return redirect(url_for('teacher_dashboard'))
    return render_template('assign_assignment.html')

# 查看作业
@app.route('/teacher/view_assignments')
@login_required('teacher')
def teacher_view_assignments():
    with DatabaseConnection() as c:
        c.execute("SELECT * FROM assignments WHERE class_id = ? ORDER BY created_at DESC", (session['class_id'],))
        assignments = c.fetchall()
    return render_template('view_assignments.html', assignments=assignments)

# 作业统计分析
@app.route('/teacher/analyze_assignment/<int:assignment_id>')
@login_required('teacher')
def teacher_analyze_assignment(assignment_id):
    with DatabaseConnection() as c:
        # 获取作业信息
        c.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
        assignment = c.fetchone()
        
        # 获取班级总学生数
        c.execute("SELECT COUNT(*) FROM users WHERE class_id = ? AND role = 'student'", (session['class_id'],))
        total_students = c.fetchone()[0]
        
        # 获取提交人数
        c.execute("SELECT COUNT(*) FROM submissions WHERE assignment_id = ?", (assignment_id,))
        submitted_count = c.fetchone()[0]
        
        # 计算完成率
        completion_rate = (submitted_count / total_students * 100) if total_students > 0 else 0
        
        # 获取评分分布
        c.execute("SELECT score, COUNT(*) FROM submissions WHERE assignment_id = ? AND score IS NOT NULL GROUP BY score", (assignment_id,))
        score_distribution = c.fetchall()
        
        # 获取未完成学生名单
        c.execute("SELECT id, name FROM users WHERE class_id = ? AND role = 'student' AND id NOT IN (SELECT student_id FROM submissions WHERE assignment_id = ?)", (session['class_id'], assignment_id))
        uncompleted_students = c.fetchall()
        
        # 获取完成学生名单
        c.execute("SELECT u.id, u.name FROM users u JOIN submissions s ON u.id = s.student_id WHERE u.class_id = ? AND u.role = 'student' AND s.assignment_id = ?", (session['class_id'], assignment_id))
        completed_students = c.fetchall()
    
    return render_template('analyze_assignment.html', 
                           assignment=assignment,
                           total_students=total_students,
                           submitted_count=submitted_count,
                           completion_rate=completion_rate,
                           score_distribution=score_distribution,
                           uncompleted_students=uncompleted_students,
                           completed_students=completed_students)

# 查看作业提交情况
@app.route('/teacher/view_submissions/<int:assignment_id>')
@login_required('teacher')
def teacher_view_submissions(assignment_id):
    with DatabaseConnection() as c:
        # 获取作业信息
        c.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
        assignment = c.fetchone()
        
        # 获取所有提交
        c.execute("SELECT s.*, u.name FROM submissions s JOIN users u ON s.student_id = u.id WHERE s.assignment_id = ?", (assignment_id,))
        submissions = c.fetchall()
    return render_template('view_submissions.html', assignment=assignment, submissions=submissions)

# 评分
@app.route('/teacher/score_submission/<int:submission_id>', methods=['POST'])
@login_required('teacher')
def teacher_score_submission(submission_id):
    score = request.form['score']
    
    with DatabaseConnection() as c:
        c.execute("UPDATE submissions SET score = ?, scorer_id = ? WHERE id = ?", (score, session['user_id'], submission_id))
    
    flash('评分成功')
    return redirect(request.referrer)

# 学生后台
@app.route('/student/dashboard')
@login_required('student')
def student_dashboard():
    with DatabaseConnection() as c:
        c.execute("SELECT * FROM assignments WHERE class_id = ? ORDER BY created_at DESC", (session['class_id'],))
        assignments = c.fetchall()
    return render_template('student_dashboard.html', assignments=assignments)

# 提交作业
# 学生提交或修改作业的处理函数
# 支持文本内容和图片上传，实现了截止日期检查和重复提交限制
@app.route('/student/submit_assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required('student')
def student_submit_assignment(assignment_id):
    with DatabaseConnection() as c:
        # 获取作业信息
        c.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
        assignment = c.fetchone()
        
        # 检查是否已过截止日期
        deadline = datetime.strptime(assignment[6], '%Y-%m-%d')
        today = datetime.now()
        if today > deadline:
            flash('作业已过截止日期，无法提交或修改')
            return redirect(url_for('student_dashboard'))
        
        # 检查是否已经提交过
        c.execute("SELECT * FROM submissions WHERE assignment_id = ? AND student_id = ?", (assignment_id, session['user_id']))
        existing_submission = c.fetchone()
        
        if request.method == 'POST':
            content = request.form['content']
            
            # 生成唯一文件名，确保文件存储安全
            base_filename = str(uuid.uuid4())
            text_file_path = None
            image_file_path = None
            
            # 保存文本内容到文件
            if content:
                text_file_path = os.path.join(UPLOAD_FOLDER, f"{base_filename}.txt")
                with open(text_file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            # 保存图片文件
            if 'file' in request.files and request.files['file'].filename != '':
                file = request.files['file']
                if allowed_file(file.filename):
                    image_extension = file.filename.split('.')[-1].lower()
                    image_file_path = os.path.join(UPLOAD_FOLDER, f"{base_filename}.{image_extension}")
                    # 规范化路径，防止路径遍历攻击
                    image_file_path = os.path.normpath(image_file_path)
                    # 确保文件保存在指定目录内
                    if not os.path.abspath(image_file_path).startswith(os.path.abspath(UPLOAD_FOLDER)):
                        flash('文件上传路径错误')
                        return redirect(url_for('student_dashboard'))
                    file.save(image_file_path)
            
            # 保存文件名到数据库（只保存基础文件名，不包含路径和扩展名）
            if existing_submission:
                # 更新现有提交
                c.execute("UPDATE submissions SET content = ?, file_path = ? WHERE id = ?", (base_filename, base_filename, existing_submission[0]))
                flash('作业修改成功')
            else:
                # 创建新提交
                c.execute("INSERT INTO submissions (assignment_id, student_id, content, file_path) VALUES (?, ?, ?, ?)", 
                          (assignment_id, session['user_id'], base_filename, base_filename))
                flash('作业提交成功')
            
            return redirect(url_for('student_dashboard'))
        
        # 如果已有提交，预填充表单
        if existing_submission:
            # 读取文本文件内容
            if existing_submission[4]:
                text_file_path = os.path.join(UPLOAD_FOLDER, f"{existing_submission[4]}.txt")
                try:
                    with open(text_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # 更新existing_submission元组，将文本内容替换为文件内容
                    existing_submission = (existing_submission[0], existing_submission[1], existing_submission[2], existing_submission[3], content, existing_submission[5], existing_submission[6], existing_submission[7], existing_submission[8], existing_submission[9])
                except Exception as e:
                    print(f"读取提交文件错误: {e}")
                    pass
    
    return render_template('submit_assignment.html', assignment=assignment, existing_submission=existing_submission)

# 组长查看同组作业
@app.route('/student/view_group_submissions/<int:assignment_id>')
@login_required('student')
def student_view_group_submissions(assignment_id):
    with DatabaseConnection() as c:
        # 检查是否是组长
        c.execute("SELECT is_group_leader FROM users WHERE id = ?", (session['user_id'],))
        is_leader = c.fetchone()[0]
        
        if not is_leader:
            flash('只有组长可以查看同组作业')
            return redirect(url_for('student_dashboard'))
        
        # 获取作业信息
        c.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
        assignment = c.fetchone()
        
        # 获取同组同学的提交
        c.execute("SELECT s.*, u.name FROM submissions s JOIN users u ON s.student_id = u.id WHERE s.assignment_id = ? AND u.group_id = ?", 
                  (assignment_id, session['group_id']))
        submissions = c.fetchall()
    return render_template('view_group_submissions.html', assignment=assignment, submissions=submissions)

# 组长评分
@app.route('/student/score_group_submission/<int:submission_id>', methods=['POST'])
@login_required('student')
def student_score_group_submission(submission_id):
    with DatabaseConnection() as c:
        # 检查是否是组长
        c.execute("SELECT is_group_leader FROM users WHERE id = ?", (session['user_id'],))
        is_leader = c.fetchone()[0]
        
        if not is_leader:
            flash('只有组长可以评分')
            return redirect(url_for('student_dashboard'))
        
        score = request.form['score']
        c.execute("UPDATE submissions SET score = ?, scorer_id = ? WHERE id = ?", (score, session['user_id'], submission_id))
    
    flash('评分成功')
    return redirect(request.referrer)

# 学生查看个人提交历史
@app.route('/student/view_my_submissions')
@login_required('student')
def student_view_my_submissions():
    with DatabaseConnection() as c:
        # 按日期分组获取提交
        c.execute("SELECT DATE(s.submitted_at) as submit_date, s.*, a.title FROM submissions s JOIN assignments a ON s.assignment_id = a.id WHERE s.student_id = ? ORDER BY submit_date DESC, submitted_at DESC", (session['user_id'],))
        submissions = c.fetchall()
    
    # 按日期分组
    submissions_by_date = {}
    for submission in submissions:
        date = submission[0]
        if date not in submissions_by_date:
            submissions_by_date[date] = []
        submissions_by_date[date].append(submission)
    return render_template('view_my_submissions.html', submissions_by_date=submissions_by_date)

# 查看提交详情
@app.route('/view_submission/<int:submission_id>')
def view_submission(submission_id):
    with DatabaseConnection() as c:
        c.execute("SELECT s.*, a.title, u.name FROM submissions s JOIN assignments a ON s.assignment_id = a.id JOIN users u ON s.student_id = u.id WHERE s.id = ?", (submission_id,))
        submission = c.fetchone()
    
    # 读取文本文件内容
    content = ''
    if submission[4]:
        text_file_path = os.path.join(UPLOAD_FOLDER, f"{submission[4]}.txt")
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
        # 查找所有可能的图片扩展名
        image_extensions = ['jpg', 'jpeg', 'png', 'gif']
        for ext in image_extensions:
            image_path = os.path.join(UPLOAD_FOLDER, f"{submission[5]}.{ext}")
            if os.path.exists(image_path):
                image_file = f"{submission[5]}.{ext}"
                break
    
    return render_template('view_submission_detail.html', submission=submission, content=content, image_file=image_file)

# 静态文件服务
@app.route('/uploads/<path:filename>')
def download_file(filename):
    # 防止路径遍历攻击
    safe_filename = os.path.basename(filename)
    return send_from_directory(UPLOAD_FOLDER, safe_filename, as_attachment=False)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)