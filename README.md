# 本地人脸识别系统

基于 Python、PySide6、InsightFace、OpenCV 和 SQLite 的 Windows 本地桌面 PoC。

## 环境

安装 64 位 Python 3.10 或 3.11，并勾选 **Add Python to PATH**。

## 安装与运行

1. 双击 `install.bat` 创建虚拟环境并安装依赖。
2. 双击 `run.bat` 启动软件。
3. 先在“人员管理”录入人员照片，再在“摄像头管理”添加并测试 RTSP，最后到“实时识别”启动。

首次使用 InsightFace 时会自动下载 `buffalo_l` 模型，需保持网络可用。模型下载后保存在项目 `models` 目录，后续可离线使用。

数据位于 `data`，日志位于 `logs`。删除人员会同步删除其人脸照片和特征。
