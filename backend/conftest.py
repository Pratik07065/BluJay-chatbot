import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) in sys.path:
    sys.path.remove(str(backend_dir))
sys.path.insert(0, str(backend_dir))
