import os
import sys
from pathlib import Path

_PYTHON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PYTHON_DIR / "src"))

# 共有ライブラリ（automation/shared/*/src）。main.py と同じ解決をする。
_default_root = _PYTHON_DIR.parents[2] / "shared"
_shared_root = Path(os.environ.get("AUTOMATION_SHARED_ROOT", _default_root))
for _library in sorted(_shared_root.glob("*/src")):
    if str(_library) not in sys.path:
        sys.path.insert(0, str(_library))
