@echo off
chcp 65001

:: 检查Python是否安装
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python 未安装，请先安装 Python。
    exit /b
)

:: 创建Python虚拟环境
python -m venv venv

:: 激活Python虚拟环境
call venv\Scripts\activate

:: 升级pip并配置镜像源
python -m pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

pause