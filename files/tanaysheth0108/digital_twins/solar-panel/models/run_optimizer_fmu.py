#!/usr/bin/env python3
"""Runtime wrapper to execute `models/optimizer.fmu` if present.

Behavior:
- If `models/optimizer.fmu` exists, the archive is extracted to a temporary
  directory and the contained `optimizer.py` is executed as a subprocess.
- If the .fmu is missing, falls back to running `models/optimizer.py`.

This avoids coupling to any specific FMU runtime while letting the
`.fmu` file act as a drop-in distribution for the optimizer code.
"""
import sys
import zipfile
import tempfile
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[0]
FMU = ROOT / "optimizer.fmu"
SRC = ROOT / "optimizer.py"

def run_script(path: Path) -> int:
    cmd = [sys.executable, str(path)]
    return subprocess.call(cmd)

def main() -> int:
    if FMU.exists():
        print(f"Found {FMU}, extracting and running optimizer from FMU...")
        with tempfile.TemporaryDirectory(prefix="optimizer_fmu_") as td:
            td_path = Path(td)
            try:
                with zipfile.ZipFile(FMU, "r") as z:
                    z.extractall(path=td)
            except zipfile.BadZipFile:
                print("Error: optimizer.fmu is not a valid zip archive.")
                return 2

            # Prefer sources/optimizer.py (conventional FMU layout)
            target = td_path / "sources" / "optimizer.py"
            if not target.exists():
                # backwards compatible: check root optimizer.py
                target = td_path / "optimizer.py"
            if not target.exists():
                print("Error: optimizer.py not found inside the FMU archive.")
                return 3
            return run_script(target)
    else:
        # Fall back to running the source file directly
        if not SRC.exists():
            print("Error: no optimizer.fmu and no optimizer.py found.")
            return 4
        print("No optimizer.fmu found — running models/optimizer.py directly.")
        return run_script(SRC)

if __name__ == "__main__":
    raise SystemExit(main())
