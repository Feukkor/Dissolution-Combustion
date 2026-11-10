# Dissolution-Combustion

北京大学-化学与分子工程学院-中级物理化学实验项目。

基于 [@ZhaoZh02](https://github.com/ZhaoZh02) 的 [数据处理程序](https://github.com/ZhaoZh02/ReynoldsCorrection) 和 [@WaterKing201030](https://github.com/WaterKing201030) 的 [数据采集程序](https://github.com/WaterKing201030/SWC-IID-Combust)。本项目采用 GPL-3.0 协议，欢迎 Issue 和 Pull Request。

## v2.2.5

本版增加了数据导入检查与原始数据保护、依据数据给出的实验阶段操作提示、同一次运行内的量热计常数记忆，并改进了拟合区间的自动选点。完整记录见 [history.md](history.md)。

Windows 用户可直接运行发布附件中的 `Dissolution-Combustion-v2.2.5.exe`，无需安装 Python。程序应放在可写的目录下运行；连接仪器仍需安装对应的 USB 串口驱动。

- [操作手册](manual/Manual.md)
- [平台时长、判据及提前操作的影响](docs/LinearBaseline-Guidance.md)
- [Windows 构建与验证](docs/Windows-Build.md)
- [自动选点的已知边界限制](docs/PointSelection-Review.md)
- [程序设计说明](docs/Document.md)

## 源码运行

在包含 `main.py` 的目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
.\.venv\Scripts\python.exe main.py
```

其他平台可安装 `requirements.txt` 中的运行依赖。
