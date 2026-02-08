import os

print("当前工作目录:", os.getcwd())
print("uploads目录绝对路径:", os.path.abspath('uploads'))
print("uploads目录是否存在:", os.path.exists('uploads'))
print("uploads目录中的文件:")
if os.path.exists('uploads'):
    for file in os.listdir('uploads'):
        print(f"  - {file}")
