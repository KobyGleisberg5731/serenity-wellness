#!/usr/bin/env python3
"""Entry point for Serenity Wellness app."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.app import app

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 18871))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
