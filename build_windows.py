"""Run with .venv/Scripts/python.exe build_windows.py."""
from pathlib import Path
import subprocess
import sys
from app_version import EXE_NAME


if __name__ == "__main__":
    if sys.platform != "win32":
        raise SystemExit("This recipe builds the Windows executable; build macOS apps on macOS.")
    project = Path(__file__).resolve().parent
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--windowed", "--name", EXE_NAME,
        "--icon", str(project / "chem.ico"),
        "--add-data", str(project / "chem.ico") + ";.",
        "--add-data", str(project / "chem.png") + ";.",
        "--distpath", str(project / "dist"),
        "--workpath", str(project / "build"),
        "--specpath", str(project / "build"),
        str(project / "main.py"),
    ], cwd=project, check=True)
