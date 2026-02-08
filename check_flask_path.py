import os
import sys
# 添加当前目录到Python路径，确保能导入app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app, PROJECT_ROOT, UPLOAD_FOLDER

print("Flask应用根路径:", app.root_path)
print("PROJECT_ROOT:", PROJECT_ROOT)
print("UPLOAD_FOLDER:", UPLOAD_FOLDER)
print("当前工作目录:", os.getcwd())
print("uploads目录绝对路径:", os.path.abspath('uploads'))
print("app.py所在目录:", os.path.dirname(os.path.abspath(__file__)))
print("UPLOAD_FOLDER目录是否存在:", os.path.exists(UPLOAD_FOLDER))
if os.path.exists(UPLOAD_FOLDER):
    print("UPLOAD_FOLDER中的文件:")
    for file in os.listdir(UPLOAD_FOLDER):
        print(f"  - {file}")
