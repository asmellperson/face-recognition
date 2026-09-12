@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_EXE=py -3.11"
    ) else (
        where python >nul 2>nul
        if errorlevel 1 (
            echo [错误] 未找到 Python。
            echo 请安装 Python 3.10 或 3.11，并勾选 Add Python to PATH。
            echo 然后双击 install.bat 安装依赖。
            pause
            exit /b 1
        )
        set "PYTHON_EXE=python"
    )
)

%PYTHON_EXE% -c "import PySide6, cv2, insightface, onnxruntime" >nul 2>nul
if errorlevel 1 (
    echo [错误] 依赖尚未安装或不完整。
    echo 请先双击 install.bat。
    pause
    exit /b 1
)

%PYTHON_EXE% main.py
if errorlevel 1 pause
