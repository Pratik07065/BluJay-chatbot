# 🚀 Blujay Technologies AI Chatbot Integration Guide

This package provides a **domain-specific AI chatbot assistant** built specifically for Blujay Technologies. It easily embeds into any existing website without modifying the existing site structure or design.

---

## ⚡ 1-Minute Web Integration (For Existing Website)

To add the chatbot to your existing website, copy and paste this **single line script tag** right before the closing `</body>` tag on any HTML page:

```html
<script src="http://localhost:5000/static/blujay-chatbot.js"></script>
```

> **Production Deployment:** Replace `http://localhost:5000` with your deployed server domain (e.g. `https://chatbot.blujaytech.com`).

---

## 🧠 Key Capabilities

1. **Zero Token Cost RAG Caching**:
   - Checks local `knowledge.json` first before calling Groq LLM API.
   - Answers instant queries with zero API token cost.

2. **Domain-Restriction Gate**:
   - Rejects non-Blujay questions (*"Who is the PM of India?"*, *"Write Python code"*) without calling Groq.

3. **Prompt Injection & Security Guard**:
   - Blocks attack prompts (*"Ignore previous instructions"*, *"Show API key"*) before processing.

4. **Zero-Hallucination Answer Validation**:
   - Verifies all generated LLM answers against context. Prevents saving fake course fees, salary packages, or guarantees.

5. **Human-in-the-Loop Admin Staging**:
   - New valid answers are staged in `pending_knowledge.json` for admin review before being added to verified knowledge.

---

## 🛠 Admin API Workflow

### Authenticate Requests
Include header:
```http
X-Admin-API-Key: blujay_admin_secret_key_2026
```

### Endpoints

- **List Pending Questions**: `GET /api/admin/pending`
- **Approve & Promote to Knowledge Base**: `POST /api/admin/approve/<entry_id>`
- **Reject Entry**: `POST /api/admin/reject/<entry_id>`
- **Edit Entry**: `PUT /api/admin/edit/<entry_id>` with JSON `{ "answer": "Updated answer text" }`

---

## 🏃 Running the Server

Start the application server:
```powershell
python server.py
```
- Server URL: `http://localhost:5000/`
- Health Check: `GET /api/health`
