@echo off
chcp 65001 >nul
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.11"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo [错误] 未找到 Python 3.10/3.11。
        echo 请先从 python.org 安装 Python，并勾选 Add Python to PATH。
        pause
        exit /b 1
    )
    set "PYTHON_CMD=python"
)

if not exist ".venv\Scripts\python.exe" (
    echo 正在创建虚拟环境...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :error
)

echo 正在升级 pip...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :error

echo 正在安装项目依赖，这可能需要数分钟...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo 安装完成。现在可以双击 run.bat 启动。
echo 首次录入或识别时，InsightFace 会下载 buffalo_l 模型。
pause
exit /b 0

:error
echo.
echo [错误] 安装失败，请检查上方错误信息和网络连接。
pause
exit /b 1
