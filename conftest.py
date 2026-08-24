import sys
from pathlib import Path

# Ensure backend directory is prioritized at sys.path[0]
root_dir = Path(__file__).resolve().parent
backend_dir = root_dir / "backend"

if str(backend_dir) in sys.path:
    sys.path.remove(str(backend_dir))
sys.path.insert(0, str(backend_dir))
