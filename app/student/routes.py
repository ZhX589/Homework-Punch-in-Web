from flask import render_template, request, redirect, url_for, session, flash, current_app
import os
import uuid
from app.student import student_bp
from app.utils.db import DatabaseConnection
from app.main.routes import login_required
from datetime import datetime

# 允许的图片扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 学生后台
@student_bp.route('/dashboard')
@login_required('student')
def dashboard():
    with DatabaseConnection() as c:
        c.execute("SELECT * FROM assignments WHERE class_id = ? ORDER BY created_at DESC", (session['class_id'],))
        assignments = c.fetchall()
    return render_template('student_dashboard.html', assignments=assignments)

# 提交作业
@student_bp.route('/submit_assignment/<int:assignment_id>', methods=['GET', 'POST'])
@login_required('student')
def submit_assignment(assignment_id):
    with DatabaseConnection() as c:
        # 获取作业信息
        c.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
        assignment = c.fetchone()
        
        # 检查是否已过截止日期
        deadline = datetime.strptime(assignment[6], '%Y-%m-%d %H:%M:%S')
        today = datetime.now()
        if today > deadline:
            flash('作业已过截止日期，无法提交或修改')
            return redirect(url_for('student.dashboard'))
        
        # 检查是否已经提交过
        c.execute("SELECT * FROM submissions WHERE assignment_id = ? AND student_id = ?", (assignment_id, session['user_id']))
        existing_submission = c.fetchone()
        
        if request.method == 'POST':
            content = request.form['content']
            
            # 生成唯一文件名，确保文件存储安全
            base_filename = str(uuid.uuid4())
            text_file_path = None
            image_file_path = None
            
            # 获取应用配置中的UPLOAD_FOLDER
            upload_folder = current_app.config['UPLOAD_FOLDER']
            
            # 保存文本内容到文件
            if content:
                text_file_path = os.path.join(upload_folder, f"{base_filename}.txt")
                with open(text_file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            # 保存图片文件
            if 'file' in request.files and request.files['file'].filename != '':
                file = request.files['file']
                if allowed_file(file.filename):
                    image_extension = file.filename.split('.')[-1].lower()
                    image_file_path = os.path.join(upload_folder, f"{base_filename}.{image_extension}")
                    # 规范化路径，防止路径遍历攻击
                    image_file_path = os.path.normpath(image_file_path)
                    # 确保文件保存在指定目录内
                    if not os.path.abspath(image_file_path).startswith(os.path.abspath(upload_folder)):
                        flash('文件上传路径错误')
                        return redirect(url_for('student.dashboard'))
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
            
            return redirect(url_for('student.dashboard'))
        
        # 如果已有提交，预填充表单
        if existing_submission:
            # 读取文本文件内容
            if existing_submission[4]:
                # 获取应用配置中的UPLOAD_FOLDER
                upload_folder = current_app.config['UPLOAD_FOLDER']
                text_file_path = os.path.join(upload_folder, f"{existing_submission[4]}.txt")
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
@student_bp.route('/view_group_submissions/<int:assignment_id>')
@login_required('student')
def view_group_submissions(assignment_id):
    with DatabaseConnection() as c:
        # 检查是否是组长
        c.execute("SELECT is_group_leader FROM users WHERE id = ?", (session['user_id'],))
        is_leader = c.fetchone()[0]
        
        if not is_leader:
            flash('只有组长可以查看同组作业')
            return redirect(url_for('student.dashboard'))
        
        # 获取作业信息
        c.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
        assignment = c.fetchone()
        
        # 获取同组同学的提交
        c.execute("SELECT s.*, u.name FROM submissions s JOIN users u ON s.student_id = u.id WHERE s.assignment_id = ? AND u.group_id = ?", 
                  (assignment_id, session['group_id']))
        submissions = c.fetchall()
    return render_template('view_group_submissions.html', assignment=assignment, submissions=submissions)

# 组长评分
@student_bp.route('/score_group_submission/<int:submission_id>', methods=['POST'])
@login_required('student')
def score_group_submission(submission_id):
    with DatabaseConnection() as c:
        # 检查是否是组长
        c.execute("SELECT is_group_leader FROM users WHERE id = ?", (session['user_id'],))
        is_leader = c.fetchone()[0]
        
        if not is_leader:
            flash('只有组长可以评分')
            return redirect(url_for('student.dashboard'))
        
        score = request.form['score']
        c.execute("UPDATE submissions SET score = ?, scorer_id = ? WHERE id = ?", (score, session['user_id'], submission_id))
    
    flash('评分成功')
    return redirect(request.referrer)

# 学生查看个人提交历史
@student_bp.route('/view_my_submissions')
@login_required('student')
def view_my_submissions():
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

# 查看作业详情
@student_bp.route('/assignment_detail/<int:assignment_id>')
@login_required('student')
def assignment_detail(assignment_id):
    with DatabaseConnection() as c:
        # 获取作业信息
        c.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
        assignment = c.fetchone()
        
        if not assignment:
            flash('作业不存在')
            return redirect(url_for('student.dashboard'))
        
        # 检查作业是否属于当前学生的班级
        if assignment[2] != session['class_id']:
            flash('无权查看此作业')
            return redirect(url_for('student.dashboard'))
    
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
                           submission_count=0,
                           total_students=0,
                           completion_rate=0)
