#!/usr/bin/env python3
"""Convenience script to generate a calendar preview image without hardware."""

import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# If running with system python, automatically switch to .venv
if sys.prefix == sys.base_prefix:
    venv_python = BASE_DIR / ".venv" / "bin" / "python3"
    if venv_python.exists():
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)

from src.main import main

if __name__ == "__main__":
    # Inject --preview argument if not already supplied
    if "--preview" not in sys.argv:
        sys.argv.append("--preview")
    main()
