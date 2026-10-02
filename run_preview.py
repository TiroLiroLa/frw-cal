#!/usr/bin/env python3
"""Convenience script to generate a calendar preview image without hardware."""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.main import main

if __name__ == "__main__":
    # Inject --preview argument if not already supplied
    if "--preview" not in sys.argv:
        sys.argv.append("--preview")
    main()
