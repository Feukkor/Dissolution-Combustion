"""Build the printable PDF of the operation manual.

Markdown -> HTML (pandoc) -> PDF (headless Chrome). The manual keeps a hand-written
table of contents whose anchors do not match generated heading ids, so that section
is dropped from the build copy and pandoc's own TOC is used instead. The source
Manual.md is left untouched.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

# The Windows CI console cannot encode the Chinese messages below, so write UTF-8.
for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / "manual"
BUILD = MANUAL / "_build"
CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def strip_toc(text):
    """Drop the hand-written 『目录』 section, keeping everything else."""
    lines = text.splitlines(keepends=True)
    out, skipping = [], False
    for line in lines:
        if re.match(r"^#\s+目录\s*$", line):
            skipping = True
            continue
        if skipping:
            if line.startswith("# "):
                skipping = False
            else:
                continue
        out.append(line)
    return "".join(out)


def find_chrome():
    for candidate in CHROME:
        if Path(candidate).exists():
            return candidate
    found = shutil.which("chrome") or shutil.which("msedge")
    if found:
        return found
    raise SystemExit("未找到 Chrome 或 Edge，无法生成 PDF")


def main():
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True)
    source = BUILD / "manual.md"
    source.write_text(strip_toc((MANUAL / "Manual.md").read_text(encoding="utf-8")), encoding="utf-8")
    html = BUILD / "manual.html"
    subprocess.run([
        "pandoc", str(source), "-f", "gfm", "-t", "html5", "-s",
        "--toc", "--toc-depth=1", "--metadata", "lang=zh-CN",
        "--metadata", "title=热力学实验辅助程序使用说明",
        "--css", "../print.css", "-o", str(html),
    ], check=True, cwd=BUILD)
    # Chrome resolves relative image paths against the HTML file, and the images
    # live one level up, so point them back to the manual directory.
    text = html.read_text(encoding="utf-8")
    text = re.sub(r'src="(?!\.\./)', 'src="../', text)
    html.write_text(text, encoding="utf-8")
    target = MANUAL / "Manual.pdf"
    subprocess.run([
        find_chrome(), "--headless", "--disable-gpu", "--no-sandbox",
        "--no-pdf-header-footer", "--print-to-pdf-no-header",
        f"--print-to-pdf={target}", html.resolve().as_uri(),
    ], check=True)
    print(f"PDF: {target} ({target.stat().st_size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    sys.exit(main())
