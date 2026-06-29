# RAG Milvus Assistant

A modular, production-oriented Retrieval-Augmented Generation system built with Python, FastAPI, Streamlit, Milvus Standalone, Sentence Transformers, Transformers, and PyMuPDF.

## Architecture

The system is split into small, focused modules so each concern can evolve independently:

- `backend/pdf/parser.py` extracts clean text from PDF pages with PyMuPDF.
- `backend/rag/chunking.py` splits page text into reusable chunks with overlap.
- `backend/rag/embeddings.py` calls Google `gemini-embedding-2` via the Gemini API (dim=1536, set `GEMINI_API_KEY` in `.env`).
- `backend/vectordb/milvus_db.py` creates and queries the Milvus collection.
- `backend/services/ingest_service.py` orchestrates PDF ingestion end-to-end.
- `backend/rag/retrieval.py` performs semantic retrieval for user questions.
- `backend/rag/prompts.py` centralizes prompt templates and context formatting.
- `backend/rag/llm.py` calls Groq chat completions for answer generation.
- `backend/rag/pipeline.py` combines retrieval, prompt assembly, and generation.
- `backend/api/routes.py` exposes the HTTP API.
- `frontend/streamlit_app.py` provides the chat UI and PDF upload flow.

## Data Flow

1. A user uploads a PDF in Streamlit.
2. The frontend sends the file to `POST /api/v1/upload`.
3. The backend parses the PDF with PyMuPDF and cleans the text.
4. The ingestion service chunks the text, embeds each chunk, and stores vectors in Milvus.
5. When the user asks a question, the backend embeds the query and performs vector search.
6. Retrieved chunks are assembled into a prompt.
7. The prompt is sent to Groq for answer generation.
8. The answer and supporting chunks are returned to the frontend.

## Why this structure scales

- Ingestion, retrieval, storage, and generation are separated, so each part can be replaced later.
- Milvus lives behind a dedicated adapter, which makes hybrid search or metadata filters easier to add.
- Embeddings and generation use external APIs (Gemini + Groq), so no local GPU is required for models.
- Settings are centralized in environment variables, which makes local development, GPU VM, and cloud deployments consistent.
- The pipeline is written so streaming, citations, and conversation memory can be added without changing the API shape.

## Local Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   Set your Google API key in `.env`:

   ```env
   GEMINI_API_KEY=your-api-key-here
   GROQ_API_KEY=your-groq-api-key-here
   EMBEDDING_MODEL_NAME=gemini-embedding-2
   LLM_MODEL=llama-3.1-8b-instant
   MILVUS_DIMENSION=1536
   ```

   If you previously indexed documents with a different embedding dimension (e.g. 1024), delete `milvus_local.db` or change `MILVUS_COLLECTION_NAME` before re-uploading PDFs.

2. Start the app locally:

- Milvus Lite is enabled by default via `MILVUS_URI=./milvus_local.db`, so no separate Milvus server is needed.
- If you want to use a remote Milvus instead, override `MILVUS_URI` with that endpoint.
- Start the backend API with Uvicorn:

   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```

- Start the Streamlit frontend (from the project root):

   ```bash
   cd /path/to/Rag_pymilvus
   streamlit run frontend/streamlit_app.py --server.port 8501
   ```

3. Open the apps:

- Streamlit UI: http://localhost:8501
- FastAPI docs: http://localhost:8000/docs
- Milvus Lite data file: `milvus_local.db`

## Groq LLM

The backend uses the Groq API for chat completion. Set `GROQ_API_KEY` and `LLM_MODEL` in `.env` (default: `llama-3.1-8b-instant`).

## Milvus Lite

The backend uses `pymilvus` with a local file URI. If `MILVUS_URI` ends with `.db`, `MilvusClient` uses Milvus Lite and stores vectors in that file. Milvus Lite only supports the `FLAT` index type, and the backend switches to `FLAT` automatically for local `.db` URIs.

## API Endpoints

- `GET /api/v1/health`
- `POST /api/v1/upload`
- `POST /api/v1/query`

## Future Extensions

The codebase is intentionally structured to make these additions straightforward:

- hybrid search
- citations
- metadata filtering
- conversation memory
- OCR
- authentication
- multi-user support
- streaming responses
- Kubernetes deployment
- Redis caching
- async ingestion pipelines

## Notes for Production

- Replace the permissive CORS setup with explicit origins.
- Add auth before exposing the API publicly.
- Consider background jobs for large ingestion workloads.
- Add observability with structured logs, metrics, and traces.
- Pin model and image versions in production for reproducibility.
