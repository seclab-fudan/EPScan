import os
import subprocess
from pathlib import Path

UPX_PATH = os.getenv('UPX_PATH', 'upx')


def upx_decompress(exe: Path) -> None:
    try:
        subprocess.run([UPX_PATH, '-d', str(exe)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        pass
