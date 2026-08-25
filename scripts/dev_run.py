import sys
import subprocess
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent.parent
    app_main = root / "python-app" / "main.py"
    subprocess.run([sys.executable, str(app_main)])

if __name__ == "__main__":
    main()
