from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
for script in [
    "src/generate_data.py",
    "src/solve.py",
    "src/make_figures.py",
    "src/build_report.py",
]:
    subprocess.run([sys.executable, str(root / script)], check=True)
