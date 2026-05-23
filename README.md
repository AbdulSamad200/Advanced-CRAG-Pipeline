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

## Architecture Diagram

%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#ffffff', 'edgeLabelBackground':'#ffffff', 'tertiaryColor': '#fff'}}}%%

graph TD
    %% --- Define Global Nodes & Shapes ---
    User(("&nbsp; User &nbsp;"))
    
    subgraph Client ["Frontend (React)"]
        UI[UI Interface]
        SSE_Rec[SSE Listener / Logs]
    end

    subgraph API ["Backend (FastAPI)"]
        Core[RAG Pipeline Manager]
        SSE_Stream(SSE Streamer)
    end

    subgraph EmbedStage ["Embedding Stage"]
        EmbedModel[gemini-embedding-001]
    end

    subgraph RetrStage ["Retrieval Stage"]
        VectorDB[Qdrant Cloud]
        PDF_Chunks[Top PDF Chunks]
    end

    subgraph RerankStage ["Primary Reranking"]
        CrossEnc[FastEmbed<br/>BGE-reranker]
    end

    %% --- Logic Decision Gate ---
    subgraph CRAG ["CRAG (Corrective RAG) Logic"]
        ScoreGate{"<b>Vector Score?</b>"}
        RelJudge{"LLM Relevance Judge<br/>(Gemini)"}
        RelDecision{Judge Decision?}
    end

    subgraph External ["External Services"]
        WebSearch[Tavily Web Search]
    end

    subgraph FuseGen ["Source Fusion & Generation"]
        Fusion[Merge PDF + Web]
        FinalRerank[Final Rerank<br/>Top 10]
        FinalContext(Final Context)
        LLM[Gemini 2.5 Flash]
    end

    %% --- Connections & Flow ---
    
    %% User to UI
    User -->|Sends Query| UI
    
    %% UI to API
    UI -->|POST /query| Core
    
    %% Real-time Feedback Flow
    Core .->|Real-time Logs| SSE_Stream
    SSE_Stream .->|Streaming (SSE)| SSE_Rec
    SSE_Rec -.->|Update Status| UI

    %% Main Pipeline Execution
    Core -->|Passes Query| EmbedModel
    EmbedModel -->|Vector Embedding| VectorDB
    VectorDB -->|Retrieved| PDF_Chunks
    PDF_Chunks -->|Re-scored| CrossEnc
    CrossEnc -->|Scored Chunks| ScoreGate

    %% CRAG Decision Paths
    %% Path 1: CORRECT (High Score)
    ScoreGate ==>|CORRECT >= 0.75| FinalContext
    
    %% Path 2: AMBIGUOUS (Mid Score)
    ScoreGate -->|AMBIGUOUS 0.50 ≤ s < 0.75| RelJudge
    RelJudge -->|Relevance?| RelDecision
    
    %% Path 3: INCORRECT (Low Score)
    ScoreGate ==>|INCORRECT < 0.50| WebSearch

    %% Sub-path decisions for AMBIGUOUS
    RelDecision ==>|Relevant| FinalContext
    RelDecision -->|Unsure| Fusion
    
    %% Fusion and Final Paths
    Fusion -->|Hybrid Sources| FinalRerank
    FinalRerank -->|Top 10 Chunks| FinalContext

    %% Generation
    FinalContext -->|Generated| LLM
    LLM -->|Synthesized Answer| Core
    Core -->|JSON Response| UI

    %% --- Styling & Themes ---

    %% Colors: 
    %%   Green: Primary Path/Fast
    %%   Blue: Logic/Internal Process
    %%   Yellow: Decision
    %%   Red: External API
    %%   Grey/Text: Secondary/Data

    classDef user fill:#E1F5FE,stroke:#01579B,stroke-width:2px,color:#01579B;
    classDef client fill:#E0F7FA,stroke:#006064,stroke-width:1px,rx:8,ry:8;
    classDef api fill:#E8EAF6,stroke:#1A237E,stroke-width:1px,rx:8,ry:8;
    classDef process fill:#f9f9f9,stroke:#ccc,stroke-width:1px;
    classDef decision fill:#FFFDE7,stroke:#FBC02D,stroke-width:2px,color:#616161,rx:5,ry:5;
    classDef external fill:#FFEBEE,stroke:#B71C1C,stroke-width:1px,stroke-dasharray: 5 5,rx:10,ry:10,color:#B71C1C;
    classDef data fill:#eee,stroke:#999,stroke-width:1px;
    classDef sse fill:#f9f9f9,stroke:#ccc,stroke-width:1px,stroke-dasharray: 3 3;

    %% Assign Classes
    class User user;
    class Client client;
    class API,Core api;
    class EmbedModel,CrossEnc,Fusion,FinalRerank,FinalContext process;
    class ScoreGate,RelJudge,RelDecision decision;
    class WebSearch,LLM,VectorDB external;
    class PDF_Chunks data;
    class SSE_Stream,SSE_Rec sse;

    %% Special Link Styles (highlighting primary path)
    linkStyle 10,14,21 stroke:#2E7D32,stroke-width:3px,fill:none; /* Fast-track lines */
    linkStyle 6,7,8 stroke:#ccc,stroke-width:1px,stroke-dasharray: 3 3; /* SSE Lines */

    
## 🚀 Getting Started

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

