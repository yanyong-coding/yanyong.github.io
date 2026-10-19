@echo off

REM 获取当前脚本所在目录
set "CURRENT_DIR=%~dp0"

REM 检查是否有 Python 环境
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到 Python 环境。请先安装 Python。
    pause
    exit /b 1
)

REM 运行主程序
python "%CURRENT_DIR%main.py"

REM 如果程序意外退出，显示错误信息
if %errorlevel% neq 0 (
    echo 程序运行出错，请检查错误信息。
    pause
    exit /b %errorlevel%
)