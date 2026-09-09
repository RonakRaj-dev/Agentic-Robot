import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
STORAGE_SERVICE_DIR = ROOT_DIR / "storage_service"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if str(STORAGE_SERVICE_DIR) not in sys.path:
    sys.path.append(str(STORAGE_SERVICE_DIR))

