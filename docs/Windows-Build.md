# Windows 构建与验证（v2.2.5）

从包含 `main.py` 的源码根目录执行以下 PowerShell 命令。需要 Python 3.12 x64；运行已打包的 EXE 不需要安装 Python。连接仪器仍需要相应 USB 串口驱动，程序应放在可写目录中运行。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tests/gui_smoke.py
.\.venv\Scripts\python.exe build_windows.py
.\.venv\Scripts\python.exe tests/packaged_smoke.py dist/Dissolution-Combustion-v2.2.5.exe
```

生成文件：`dist/Dissolution-Combustion-v2.2.5.exe`。版本由 `app_version.py` 统一管理。图标、Tk 和科学计算依赖随单文件 EXE 打包；不要将虚拟环境、build、dist、缓存或实验原始数据提交到源码仓库，EXE 可作为发布附件分发。

本版 Windows 依赖锁定于 `requirements-windows.txt`，使用 SciPy 1.14.1、NumPy 2.2.6、Matplotlib 3.9.4、ttkbootstrap 1.10.1 和 PyInstaller 6.22.3。积分采用 `simpson(..., x=...)`；源码也已在 SciPy 1.13.1 下回归验证。实际构建使用 Python 3.12.4 x64。

验证范围包括主程序 63 项单元测试、真实 Tk 的彩虹提示出现与撤销、原始数据导入、两类实验计算、拟合及 CSV/PNG 导出。`packaged_smoke.py` 清除 Python 相关环境变量并缩减 PATH，检查指定 EXE 的版本窗口和正常退出。此检查不等于实际串口仪器验证。
