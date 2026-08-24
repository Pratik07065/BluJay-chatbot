# Blujay Technologies - Production-Ready AI Inquiry Chatbot

A domain-specific AI chatbot built for [Blujay Technologies](https://www.blujaytech.com/) that answers ONLY inquiries related to Blujay's institute, courses, training programs, curriculum, duration, fees, placement support, admissions, location, and contact information.

## Key Features

1. **Strict Domain Enforcement**: Out-of-domain queries (politics, general coding, weather, jokes, sports) are immediately rejected by a local relevance gate before calling Groq.
2. **Zero-Token Local KB Lookup**: Utilizes a local JSON knowledge base (`knowledge_base.json`) with hybrid Fuzzy + TF-IDF Cosine similarity matching ($\ge 82\%$ threshold). Matches return stored answers with 0 LLM token cost.
3. **Groq RAG Integration**: Unmatched queries pass through Groq (`llama-3.3-70b-versatile` at `temperature: 0.0`) constrained strictly to `blujay_context.json`.
4. **Auto-Learning KB**: New valid questions answered by Groq are saved back into `knowledge_base.json` atomically for future zero-cost hits.
5. **Private Credentials**: Groq API key is stored securely in `backend/.env`.
6. **Decoupled Modern Frontend**: Responsive UI with quick prompt pills, badges indicating source (KB Hit vs AI), and markdown formatting.

## Installation & Setup

1. **Clone/Navigate to Project**:
   ```bash
   cd "c:/Users/prati/Desktop/Python/blujay chatbot"
   ```

2. **Activate Virtual Environment**:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Set Groq API Key** (`backend/.env`):
   ```env
   GROQ_API_KEY=gsk_your_actual_groq_api_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   SIMILARITY_THRESHOLD=0.82
   ```

5. **Run the Application**:
   ```bash
   python backend/run.py
   ```
   Open your browser at `http://127.0.0.1:8000`.

## Testing

Run unit & integration test suite:
```powershell
python -m pytest backend/tests
```

Run live endpoint verification:
```powershell
python backend/tests/verify_live.py
```
