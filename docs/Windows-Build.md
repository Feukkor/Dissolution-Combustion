# Windows 构建与验证

本次环境为 CPython 3.12.10 x64，项目虚拟环境是 `.venv`，基础解释器位于 `.python-runtime`。不要删除基础解释器目录，否则虚拟环境需要重建。均不纳入 Git。

`requirements-windows.txt` 固定了本次验证使用的直接及间接依赖。原项目使用的 `scipy.integrate.simps` 和 Matplotlib `tostring_rgb` 在较新版本中已移除，因此本构建采用 SciPy 1.13.1、Matplotlib 3.8.4、NumPy 1.26.4，而不是无版本限制地升级。

在项目目录使用 PowerShell：

```powershell
# 仅在新环境首次创建时运行
.\.python-runtime\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt

# 验证依赖、回归测试和真实 Tk 界面（无串口硬件）
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tests/gui_smoke.py

# 运行源码
.\.venv\Scripts\python.exe main.py

# 打包单文件 Windows EXE
.\.venv\Scripts\python.exe build_windows.py
.\.venv\Scripts\python.exe tests/packaged_smoke.py dist/Dissolution-Combustion-v2.2.5-test.2.exe
```

生成文件：`dist/Dissolution-Combustion-v2.2.5-test.2.exe`。窗口标题包含 `v2.2.5-test.2`，版本标识集中在 `app_version.py` 中。交付副本和说明放在 `releases/v2.2.5-test.2/`。应用图标使用 `chem.ico`；图标和 Tk、NumPy、SciPy 等运行依赖已内置，目标电脑不需要安装 Python。串口仪器仍可能需要安装其 USB 驱动。

2026-09-22 验证结果：35 项回归测试通过；真实 Tk 界面的采集按钮、彩虹动画、溶解热和燃烧热模拟曲线计算、积分溶解热拟合、CSV/PNG 输出及异常文件提示通过。新增常数缓存已验证重新加载、切换功能、重置拟合、再次标定以及样品手动覆盖等行为。此前 test.1 的实物设备测试由用户反馈通过；新增功能仍需用户实机确认。

EXE 约 70.6 MiB，具体以构建产物为准。体积取决于 Python、科学计算库及打包工具版本，不能仅按旧包体积判断是否正常。

PyInstaller 不提供 Windows 到 macOS 的原生交叉打包。本项目的 macOS `.app` 应在 macOS 主机或 macOS CI 上安装依赖、构建并验证。
