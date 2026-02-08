import sqlite3
import os

# 数据库连接上下文管理器
class DatabaseConnection:
    def __enter__(self):
        self.conn = sqlite3.connect('todo_school.db')
        self.c = self.conn.cursor()
        return self.c
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        self.conn.close()

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
                 deadline DATETIME NOT NULL,
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

# 重置数据库
def reset_db():
    # 删除数据库文件
    if os.path.exists('todo_school.db'):
        os.remove('todo_school.db')
    # 重新初始化数据库
    init_db()
