# 🚀 Advanced-CRAG-Pipeline

A production-ready **Corrective RAG (CRAG)** system featuring a two-stage reranking engine and autonomous retrieval evaluation. This application intelligently decides between local PDF knowledge and real-time Web Search fallback to ensure high-precision, hallucination-free AI responses.



---

## 🌟 Key Features

### 🧠 Intelligent CRAG Orchestration
Uses a **three-zone confidence model** to evaluate retrieval quality:
- **CORRECT**: PDF context is sufficient; skips web search.
- **AMBIGUOUS**: Triggers a hybrid search (PDF + Web) and uses an LLM judge to verify relevance.
- **INCORRECT**: Discards poor PDF matches and relies entirely on Web Search.

### 🔄 Dual-Stage Reranking Pipeline
1. **Primary PDF Rerank**: Refines Top-20 vector results from Qdrant into the Top-5 most relevant chunks.
2. **Source Fusion Rerank**: If web search is activated, the system merges PDF and Web results into a single pool and reranks them all together to ensure the absolute best context reaches the LLM.

### ⚡ Real-Time Pipeline Visualization
Features a custom SSE (Server-Sent Events) streaming engine that captures backend pipeline logs and visualizes the internal "thought process" in the UI log panel in real-time.

### 🌐 Hybrid Search
Seamlessly integrated with **Tavily Search API** for deep web retrieval when local documents don't provide the answer.

---

## 🏗️ Technical Stack

- **LLM:** Google Gemini 2.5 Flash
- **Embeddings:** Gemini-Embedding-001
- **Vector DB:** Qdrant Cloud
- **Reranker:** BGE-Reranker-Base (via FastEmbed)
- **Web Search:** Tavily API
- **Backend:** FastAPI (Python)
- **Frontend:** React + Vite + TailwindCSS

---

## 🏗️ System Architecture

![RAG Architecture](https://github.com/yourusername/Advanced-CRAG-Pipeline/blob/main/Chatflow.png?raw=true)


The system follows a high-precision **Corrective RAG (CRAG)** architecture designed for enterprise-grade accuracy:

1.  **Ingestion & Retrieval**: Queries are embedded via `gemini-embedding-001` and matched against **Qdrant Cloud**.
2.  **Primary Reranking**: We use **FastEmbed (BGE-Reranker)** to perform a cross-encoder pass on the top 20 candidates, narrowing them down to a highly relevant Top 5.
3.  **Autonomous Evaluation (CRAG)**: 
    *   **CORRECT**: High-confidence PDF matches bypass the web.
    *   **AMBIGUOUS**: Triggers a **Gemini-powered Relevance Judge**. If the judge is unsure, it activates a **Hybrid Search** (Local PDF + Tavily Web).
    *   **INCORRECT**: Low-confidence PDF results are discarded, and the system pivots to **Web Search** only.
4.  **Source Fusion**: Final contexts (PDF + Web) are merged and reranked one last time to pick the absolute top 10 chunks.
5.  **Generation**: **Gemini 2.5 Flash** synthesizes the final response while the backend streams real-time "Thought Logs" via **SSE**.

---

## 🛠️ Technical Stack

### 1. Prerequisites
- Python 3.10+
- Node.js & npm
- API Keys for: Google AI Studio (Gemini), Qdrant Cloud, and Tavily.

### 2. Backend Setup
```bash
# Clone the repository
git clone https://github.com/yourusername/Advanced-CRAG-Pipeline.git
cd Advanced-CRAG-Pipeline

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure Environment Variables
# Create a .env file in the root directory:
GEMINI_API_KEY=your_key
QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_key
TAVILY_API_KEY=your_tavily_key

# Run the server
python app.py
```

### 3. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Run in development mode
npm run dev
```
The frontend will be available at `http://localhost:5173`.

---

## 🛠️ Configuration
You can tune the system performance in `config.py`:
- `CRAG_HIGH_THRESHOLD`: (Default: 0.75) Confidence needed to skip web search.
- `CRAG_LOW_THRESHOLD`: (Default: 0.50) Score below which PDF results are discarded.
- `TOP_K_RETRIEVE`: Initial candidates pulled from vector DB (Default: 20).
- `MAX_CONTEXT_CHUNKS`: Final context window size for the LLM.

---

