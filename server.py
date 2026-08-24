import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from flask_app import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    print(f"Starting Blujay Technologies AI Chatbot Server on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
