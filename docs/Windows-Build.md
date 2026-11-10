# Windows 构建与验证（v2.2.5）

在包含 `main.py` 的源码根目录下执行以下 PowerShell 命令。构建需要 Python 3.12 x64；运行已打包的 EXE 不需要安装 Python。连接仪器仍然需要对应的 USB 串口驱动，程序应放在可写的目录中运行。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tests/gui_smoke.py
.\.venv\Scripts\python.exe tests/menu_switch_smoke.py
.\.venv\Scripts\python.exe build_windows.py
.\.venv\Scripts\python.exe tests/packaged_smoke.py dist/Dissolution-Combustion-v2.2.5.exe
```

生成的文件是 `dist/Dissolution-Combustion-v2.2.5.exe`，版本号统一在 `app_version.py` 中维护。图标、Tk 和科学计算依赖都会打进单文件 EXE。虚拟环境、build、dist、缓存和实验原始数据不要提交到源码仓库，EXE 可以放在发布附件里分发。

本版 Windows 依赖锁定在 `requirements-windows.txt`，使用 SciPy 1.14.1、NumPy 2.2.6、Matplotlib 3.9.4、ttkbootstrap 1.10.1 和 PyInstaller 6.22.3。积分使用 `simpson(..., x=...)`，源码也在 SciPy 1.13.1 下做过回归验证。实际构建使用 Python 3.12.4 x64。

验证内容主要有主程序的 63 项单元测试、真实 Tk 下彩虹提示的出现与撤销、原始数据导入、两类实验的计算、拟合以及 CSV/PNG 导出。`menu_switch_smoke.py` 会在真实窗口里展开模式下拉菜单并逐个选择，确认切换后事件循环仍在响应；它会操作真实的鼠标和键盘，运行期间请不要碰电脑。`packaged_smoke.py` 会清掉 Python 相关的环境变量并缩减 PATH，然后检查指定 EXE 能正常显示主窗口并退出。这些检查都不等同于接上串口仪器后的实测。
