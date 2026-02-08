from flask import render_template, request, redirect, url_for, session, flash
import csv
from app.admin import admin_bp
from app.utils.db import DatabaseConnection
from app.main.routes import login_required, hash_password
from datetime import datetime

# 管理员后台
@admin_bp.route('/dashboard')
@login_required('admin')
def dashboard():
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
@admin_bp.route('/add_teacher', methods=['GET', 'POST'])
@login_required('admin')
def add_teacher():
    if request.method == 'POST':
        name = request.form['name']
        class_id = request.form['class_id']
        password = request.form['password']
        
        with DatabaseConnection() as c:
            c.execute("INSERT INTO users (name, class_id, role, password) VALUES (?, ?, 'teacher', ?)", (name, class_id, hash_password(password)))
        
        flash('教师添加成功')
        return redirect(url_for('admin.dashboard'))
    return render_template('add_teacher.html')

# 添加学生
@admin_bp.route('/add_student', methods=['GET', 'POST'])
@login_required('admin')
def add_student():
    if request.method == 'POST':
        name = request.form['name']
        class_id = request.form['class_id']
        group_id = request.form['group_id']
        id_card_last8 = request.form['id_card_last8']
        
        with DatabaseConnection() as c:
            c.execute("INSERT INTO users (name, class_id, group_id, id_card_last8, role) VALUES (?, ?, ?, ?, 'student')", (name, class_id, group_id, id_card_last8))
        
        flash('学生添加成功')
        return redirect(url_for('admin.dashboard'))
    return render_template('add_student.html')

# 通过CSV添加学生
@admin_bp.route('/import_students', methods=['GET', 'POST'])
@login_required('admin')
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
                        class_id = row[1].strip()
                        group_id = row[2].strip()
                        id_card_last8 = row[3].strip()
                        
                        c.execute("INSERT INTO users (name, class_id, group_id, id_card_last8, role) VALUES (?, ?, ?, ?, 'student')", (name, class_id, group_id, id_card_last8))
            
            flash('学生导入成功')
            return redirect(url_for('admin.dashboard'))
    return render_template('import_students.html')

# 管理员查看所有学生
@admin_bp.route('/view_students')
@login_required('admin')
def view_students():
    with DatabaseConnection() as c:
        c.execute("SELECT * FROM users WHERE role = 'student' ORDER BY class_id, name, id_card_last8")
        students = c.fetchall()
    return render_template('admin_view_students.html', students=students)

# 管理员查看所有教师
@admin_bp.route('/view_teachers')
@login_required('admin')
def view_teachers():
    with DatabaseConnection() as c:
        c.execute("SELECT * FROM users WHERE role = 'teacher' ORDER BY class_id, name")
        teachers = c.fetchall()
    return render_template('admin_view_teachers.html', teachers=teachers)

# 综合查看
@admin_bp.route('/view_dashboard')
@login_required('admin')
def view_dashboard():
    with DatabaseConnection() as c:
        # 获取总学生数
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'student'")
        total_students = c.fetchone()[0]
        
        # 获取总教师数
        c.execute("SELECT COUNT(*) FROM users WHERE role = 'teacher'")
        total_teachers = c.fetchone()[0]
        
        # 获取总作业数
        c.execute("SELECT COUNT(*) FROM assignments")
        total_assignments = c.fetchone()[0]
        
        # 获取总提交数
        c.execute("SELECT COUNT(*) FROM submissions")
        total_submissions = c.fetchone()[0]
        
        # 获取学生信息
        c.execute("SELECT * FROM users WHERE role = 'student' ORDER BY class_id, name, id_card_last8")
        students = c.fetchall()
        
        # 获取教师信息
        c.execute("SELECT * FROM users WHERE role = 'teacher' ORDER BY class_id, name")
        teachers = c.fetchall()
        
        # 获取作业信息
        c.execute("SELECT * FROM assignments ORDER BY deadline DESC")
        assignments = c.fetchall()
        
        # 计算每个作业的提交率
        assignment_data = []
        for assignment in assignments:
            assignment_id = assignment[0]
            c.execute("SELECT COUNT(*) FROM submissions WHERE assignment_id = ?", (assignment_id,))
            submission_count = c.fetchone()[0]
            completion_rate = (submission_count / total_students * 100) if total_students > 0 else 0
            assignment_data.append({
                'id': assignment_id,
                'title': assignment[3],
                'assigned_date': assignment[7],
                'due_date': assignment[6],
                'completion_rate': completion_rate
            })
        
        # 获取提交时间数据
        c.execute("SELECT DATE(submitted_at) as date, COUNT(*) as count FROM submissions GROUP BY DATE(submitted_at) ORDER BY date")
        submission_stats = c.fetchall()
        submission_dates = [stat[0] for stat in submission_stats]
        submission_counts = [stat[1] for stat in submission_stats]
        
        # 获取班级提交数
        c.execute("SELECT u.class_id, COUNT(*) as count FROM submissions s JOIN users u ON s.student_id = u.id GROUP BY u.class_id ORDER BY u.class_id")
        class_stats = c.fetchall()
        class_names = [stat[0] for stat in class_stats]
        class_submission_counts = [stat[1] for stat in class_stats]
    
    return render_template('admin_view_dashboard.html', 
                           total_students=total_students,
                           total_teachers=total_teachers,
                           total_assignments=total_assignments,
                           total_submissions=total_submissions,
                           students=students,
                           teachers=teachers,
                           assignments=assignment_data,
                           submission_dates=submission_dates,
                           submission_counts=submission_counts,
                           class_names=class_names,
                           class_submission_counts=class_submission_counts)

# 重置系统
@admin_bp.route('/reset_system', methods=['GET', 'POST'])
@login_required('admin')
def reset_system():
    if request.method == 'POST':
        # 重置数据库
        from app.utils.db import reset_db
        reset_db()
        
        # 清理上传文件
        import os
        upload_folder = 'uploads'
        if os.path.exists(upload_folder):
            for file in os.listdir(upload_folder):
                file_path = os.path.join(upload_folder, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        
        flash('系统重置成功')
        return redirect(url_for('admin.dashboard'))
    return render_template('reset_system.html')

# 查看作业详情
@admin_bp.route('/assignment_detail/<int:assignment_id>')
@login_required('admin')
def assignment_detail(assignment_id):
    with DatabaseConnection() as c:
        # 获取作业信息
        c.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
        assignment = c.fetchone()
        
        if not assignment:
            flash('作业不存在')
            return redirect(url_for('admin.dashboard'))
        
        # 获取提交数
        c.execute("SELECT COUNT(*) FROM submissions WHERE assignment_id = ?", (assignment_id,))
        submission_count = c.fetchone()[0]
        
        # 获取班级学生数
        c.execute("SELECT COUNT(*) FROM users WHERE class_id = ? AND role = 'student'", (assignment[2],))
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
