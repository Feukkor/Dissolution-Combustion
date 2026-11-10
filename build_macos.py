"""Run with python build_macos.py on macOS.

Produces dist/Dissolution-Combustion-v{版本}.app, a single-file .app bundle.
"""
from pathlib import Path
import subprocess
import sys
from app_version import EXE_NAME


if __name__ == "__main__":
    if sys.platform != "darwin":
        raise SystemExit("This recipe builds the macOS app; build the Windows executable on Windows.")
    project = Path(__file__).resolve().parent
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--windowed", "--name", EXE_NAME,
        "--icon", str(project / "chem.icns"),
        # macOS uses ":" as the --add-data separator, unlike ";" on Windows.
        "--add-data", str(project / "chem.icns") + ":.",
        "--add-data", str(project / "chem.png") + ":.",
        "--distpath", str(project / "dist"),
        "--workpath", str(project / "build"),
        "--specpath", str(project / "build"),
        str(project / "main.py"),
    ], cwd=project, check=True)
