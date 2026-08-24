import os
import sys
import time
import logging
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from flask import Flask, request, jsonify, send_from_directory

from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from chatbot import process_question

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [FlaskAPI] %(message)s"
)
logger = logging.getLogger("BlujayFlaskAPI")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

# Initialize Flask app pointing static_folder to frontend/
app = Flask(
    __name__,
    static_folder=str(FRONTEND_DIR),
    static_url_path="/static"
)


# Request Payload Size Limit (1 MB)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

# CORS Setup - Restrict origins
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
ALLOWED_ORIGINS = [FRONTEND_ORIGIN, "http://localhost:3000", "http://127.0.0.1:5500", "http://localhost:5173"]

CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

# Rate Limiting Setup
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per hour"],
    storage_uri="memory://"
)

# -------------------------- Error Handlers --------------------------

@app.errorhandler(400)
def handle_bad_request(e):
    msg = e.description if hasattr(e, 'description') else str(e)
    return jsonify({"error": "Bad Request", "message": msg}), 400

@app.errorhandler(413)
def handle_payload_too_large(e):
    return jsonify({"error": "Payload Too Large", "message": "Request payload exceeds maximum 1MB limit."}), 413

@app.errorhandler(429)
def handle_rate_limit(e):
    return jsonify({"error": "Rate Limit Exceeded", "message": "Too many requests. Please try again later."}), 429

@app.errorhandler(404)
def handle_not_found(e):
    return jsonify({"error": "Not Found", "message": "The requested endpoint does not exist."}), 404

@app.errorhandler(405)
def handle_method_not_allowed(e):
    return jsonify({"error": "Method Not Allowed", "message": "HTTP method not supported for this endpoint."}), 405

@app.errorhandler(Exception)
def handle_internal_error(e):
    logger.exception(f"Unhandled exception occurred during request processing: {e}")
    return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred. Please try again later."}), 500

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/health", methods=["GET"])
def health_check():

    """
    Health check endpoint returning status ok.
    """
    return jsonify({"status": "ok"}), 200

@app.route("/api/chat", methods=["POST"])
@limiter.limit("30 per minute")
def chat_endpoint():
    """
    Main chat API route.
    Validates request payload, delegates processing to chatbot.process_question(),
    and returns standardized JSON response.
    """
    start_time = time.perf_counter()

    if not request.is_json:
        return jsonify({"error": "Invalid Request", "message": "Content-Type must be application/json."}), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Invalid Request", "message": "Request body must be a valid JSON object."}), 400

    question = data.get("question")
    if question is None or not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Invalid Request", "message": "Question field is required and cannot be empty."}), 400

    raw_question = question.strip()

    try:
        res = process_question(raw_question)
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        response_payload = {
            "answer": res.get("answer", ""),
            "source": res.get("source", "fallback"),
            "cached": res.get("cached", False),
            "groq_called": res.get("groq_called", False),
            "category": res.get("category", "general")
        }

        return jsonify(response_payload), 200


    except Exception as e:
        logger.exception(f"Error processing question: {e}")
        return jsonify({"error": "Internal Server Error", "message": "Failed to process chat question."}), 500

from functools import wraps
from app.core.knowledge_manager import pending_kb_manager, ADMIN_API_KEY


def require_admin_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get("X-Admin-API-Key")
        auth_header = request.headers.get("Authorization")
        
        token = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            
        if (api_key and api_key == ADMIN_API_KEY) or (token and token == ADMIN_API_KEY):
            return f(*args, **kwargs)
            
        return jsonify({"error": "Unauthorized", "message": "Admin API key or Bearer token is missing or invalid."}), 401
    return decorated

# -------------------------- Admin Knowledge Workflow API --------------------------

@app.route("/api/admin/pending", methods=["GET"])
@require_admin_auth
def admin_list_pending():
    status_filter = request.args.get("status", "pending")
    entries = pending_kb_manager.list_pending(status=status_filter if status_filter != "all" else None)
    return jsonify({
        "status": "ok",
        "count": len(entries),
        "pending_entries": entries
    }), 200

@app.route("/api/admin/approve/<entry_id>", methods=["POST"])
@require_admin_auth
def admin_approve_entry(entry_id):
    promoted = pending_kb_manager.approve_and_promote(entry_id)
    if not promoted:
        return jsonify({"error": "Not Found", "message": f"Pending entry '{entry_id}' not found."}), 404
    return jsonify({
        "status": "ok",
        "message": f"Entry '{entry_id}' approved and promoted to verified knowledge base.",
        "entry": promoted
    }), 200

@app.route("/api/admin/reject/<entry_id>", methods=["POST"])
@require_admin_auth
def admin_reject_entry(entry_id):
    rejected = pending_kb_manager.reject_pending(entry_id)
    if not rejected:
        return jsonify({"error": "Not Found", "message": f"Pending entry '{entry_id}' not found."}), 404
    return jsonify({
        "status": "ok",
        "message": f"Entry '{entry_id}' rejected successfully.",
        "entry_id": entry_id
    }), 200

@app.route("/api/admin/edit/<entry_id>", methods=["PUT"])
@require_admin_auth
def admin_edit_entry(entry_id):
    if not request.is_json:
        return jsonify({"error": "Invalid Request", "message": "Content-Type must be application/json."}), 400

    data = request.get_json(silent=True) or {}
    new_answer = data.get("answer")
    new_category = data.get("category")

    updated = pending_kb_manager.edit_pending(entry_id, new_answer=new_answer, new_category=new_category)
    if not updated:
        return jsonify({"error": "Not Found", "message": f"Pending entry '{entry_id}' not found."}), 404

    return jsonify({
        "status": "ok",
        "message": f"Entry '{entry_id}' updated successfully.",
        "entry": updated
    }), 200

@app.route("/api/admin/promote/<entry_id>", methods=["POST"])
@require_admin_auth
def admin_promote_entry(entry_id):
    promoted = pending_kb_manager.approve_and_promote(entry_id)
    if not promoted:
        return jsonify({"error": "Not Found", "message": f"Pending entry '{entry_id}' not found."}), 404
    return jsonify({
        "status": "ok",
        "message": f"Entry '{entry_id}' promoted to verified knowledge base.",
        "entry": promoted
    }), 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)

