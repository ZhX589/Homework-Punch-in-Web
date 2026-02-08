from flask import render_template, request, redirect, url_for, session, flash, current_app
import csv
import os
import uuid
from app.teacher import teacher_bp
from app.utils.db import DatabaseConnection
from app.main.routes import login_required
from datetime import datetime

# 允许的图片扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 教师后台
@teacher_bp.route('/dashboard')
@login_required('teacher')
def dashboard():
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
@teacher_bp.route('/add_student', methods=['GET', 'POST'])
@login_required('teacher')
def add_student():
    if request.method == 'POST':
        name = request.form['name']
        class_id = session['class_id']
        group_id = request.form['group_id']
        id_card_last8 = request.form['id_card_last8']
        
        with DatabaseConnection() as c:
            c.execute("INSERT INTO users (name, class_id, group_id, id_card_last8, role) VALUES (?, ?, ?, ?, 'student')", (name, class_id, group_id, id_card_last8))
        
        flash('学生添加成功')
        return redirect(url_for('teacher.dashboard'))
    return render_template('teacher_add_student.html')

# 教师通过CSV添加学生
@teacher_bp.route('/import_students', methods=['GET', 'POST'])
@login_required('teacher')
def import_students():
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
            return redirect(url_for('teacher.dashboard'))
    return render_template('teacher_import_students.html')

# 教师查看本班学生
@teacher_bp.route('/view_students')
@login_required('teacher')
def view_students():
    with DatabaseConnection() as c:
        c.execute("SELECT * FROM users WHERE role = 'student' AND class_id = ? ORDER BY class_id, name, id_card_last8", (session['class_id'],))
        students = c.fetchall()
    return render_template('teacher_view_students.html', students=students)

# 布置作业
@teacher_bp.route('/assign_assignment', methods=['GET', 'POST'])
@login_required('teacher')
def assign_assignment():
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
                # 获取应用配置中的UPLOAD_FOLDER
                upload_folder = current_app.config['UPLOAD_FOLDER']
                # 确保路径安全
                file_path = os.path.join(upload_folder, filename)
                # 规范化路径，防止路径遍历
                file_path = os.path.normpath(file_path)
                # 确保文件保存在指定目录内
                if not os.path.abspath(file_path).startswith(os.path.abspath(upload_folder)):
                    flash('文件上传路径错误')
                    return redirect(url_for('teacher.dashboard'))
                file.save(file_path)
        
        # 转换datetime-local格式为数据库DATETIME格式
        if deadline:
            deadline = deadline.replace('T', ' ')
            deadline += ':00'

        with DatabaseConnection() as c:
            c.execute("INSERT INTO assignments (teacher_id, class_id, title, content, file_path, deadline) VALUES (?, ?, ?, ?, ?, ?)", 
                      (session['user_id'], session['class_id'], title, content, file_path, deadline))
        
        flash('作业布置成功')
        return redirect(url_for('teacher.dashboard'))
    return render_template('assign_assignment.html')

# 查看作业
@teacher_bp.route('/view_assignments')
@login_required('teacher')
def view_assignments():
    with DatabaseConnection() as c:
        c.execute("SELECT * FROM assignments WHERE class_id = ? ORDER BY created_at DESC", (session['class_id'],))
        assignments = c.fetchall()
    return render_template('view_assignments.html', assignments=assignments)

# 作业统计分析
@teacher_bp.route('/analyze_assignment/<int:assignment_id>')
@login_required('teacher')
def analyze_assignment(assignment_id):
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
@teacher_bp.route('/view_submissions/<int:assignment_id>')
@login_required('teacher')
def view_submissions(assignment_id):
    with DatabaseConnection() as c:
        # 获取作业信息
        c.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
        assignment = c.fetchone()
        
        # 获取所有提交
        c.execute("SELECT s.*, u.name FROM submissions s JOIN users u ON s.student_id = u.id WHERE s.assignment_id = ?", (assignment_id,))
        submissions = c.fetchall()
    return render_template('view_submissions.html', assignment=assignment, submissions=submissions)

# 评分
@teacher_bp.route('/score_submission/<int:submission_id>', methods=['POST'])
@login_required('teacher')
def score_submission(submission_id):
    score = request.form['score']
    
    with DatabaseConnection() as c:
        c.execute("UPDATE submissions SET score = ?, scorer_id = ? WHERE id = ?", (score, session['user_id'], submission_id))
    
    flash('评分成功')
    return redirect(request.referrer)

# 查看作业详情
@teacher_bp.route('/assignment_detail/<int:assignment_id>')
@login_required('teacher')
def assignment_detail(assignment_id):
    with DatabaseConnection() as c:
        # 获取作业信息
        c.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
        assignment = c.fetchone()
        
        if not assignment:
            flash('作业不存在')
            return redirect(url_for('teacher.dashboard'))
        
        # 检查作业是否属于当前教师的班级
        if assignment[2] != session['class_id']:
            flash('无权查看此作业')
            return redirect(url_for('teacher.dashboard'))
        
        # 获取提交数
        c.execute("SELECT COUNT(*) FROM submissions WHERE assignment_id = ?", (assignment_id,))
        submission_count = c.fetchone()[0]
        
        # 获取班级学生数
        c.execute("SELECT COUNT(*) FROM users WHERE class_id = ? AND role = 'student'", (session['class_id'],))
        total_students = c.fetchone()[0]
        
        # 计算提交率
        completion_rate = (submission_count / total_students * 100) if total_students > 0 else 0
    
    # 将元组转换为字典，方便模板访问
    assignment_dict = {
        'id': assignment[0],
        'teacher_id': assignment[1],
        'class_id': assignment[2],
        'title': assignment[3],
        'content': assignment[4],
        'file_path': assignment[5],
        'deadline': assignment[6],
        'created_at': assignment[7]
    }
    
    return render_template('assignment_detail.html', 
                           assignment=assignment_dict,
                           submission_count=submission_count,
                           total_students=total_students,
                           completion_rate=completion_rate)
