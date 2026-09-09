import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

print("Sys path:", sys.path)
try:
    import services
    print("Services package file:", getattr(services, "__file__", "No __file__"))
    import services.redis_pubsub
    print("Successfully imported services.redis_pubsub")
except Exception as e:
    print("Import failed:", e)
