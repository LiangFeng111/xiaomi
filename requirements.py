import subprocess
import sys

def install_requirements():
    print("正在安装所需软件包……")
    requirements = [
        'asyncio',
        'requests',
    ]
    
    for package in requirements:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    
    print("\n所需组件已成功安装！")

if __name__ == "__main__":
    install_requirements()