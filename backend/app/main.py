import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.models.schemas import ChatRequest, ChatResponse
from app.core.kb_manager import KnowledgeBaseManager
from app.core.chatbot import process_question
from app.config import OUT_OF_DOMAIN_RESPONSE, FALLBACK_RESPONSE

app = FastAPI(
    title="Blujay Technologies AI Inquiry Chatbot API",
    description="Domain-specific AI Chatbot API for Blujay Technologies",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize core services
kb_manager = KnowledgeBaseManager()

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "Blujay AI Chatbot",
        "kb_pairs_count": len(kb_manager.kb_data.qa_pairs)
    }

@app.get("/api/kb")
def get_knowledge_base_stats():
    return {
        "version": kb_manager.kb_data.version,
        "last_updated": kb_manager.kb_data.last_updated,
        "total_qa_pairs": len(kb_manager.kb_data.qa_pairs),
        "categories": list(set(p.category for p in kb_manager.kb_data.qa_pairs))
    }

@app.post("/api/chat", response_model=ChatResponse)
def process_chat(request: ChatRequest):
    query = request.question.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    res = process_question(query)

    is_relevant = not (res["category"] == "out_of_domain" or OUT_OF_DOMAIN_RESPONSE in res["answer"])
    source = "relevance_filter" if not is_relevant else res["source"]

    return ChatResponse(
        question=query,
        answer=res["answer"],
        source=source,
        is_relevant=is_relevant,
        confidence_score=res["confidence"],
        cost_saved=not res["groq_called"]
    )




# Serve Frontend static files
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def serve_frontend():
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Blujay AI Chatbot API is running. Frontend index.html not found."}
