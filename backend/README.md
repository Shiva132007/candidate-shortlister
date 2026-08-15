# AI-Screening Enginee — Backend Service

This directory contains the Python FastAPI backend engine and candidate shortlisting algorithm files.

## Project Structure

```
backend/
├── server.py                   # FastAPI application server and REST endpoints
├── rank.py                     # Candidate ranking and scoring engine
├── auth_db.py                  # SQLite authentication & session management
├── embed_candidates.py         # Batch SentenceTransformer embedding generator
├── embed_candidates_multi.py   # Multi-threaded embedding generator
├── requirements.txt            # Python dependencies
└── run_debug.py                # Local debug test script
```

## Running the Backend Server

```bash
# From root or backend directory
python server.py
# or
uvicorn backend.server:app --reload --port 8000
```

## Running the Ranker Script

```bash
python rank.py --candidates candidates_sample.jsonl --out team_submission_sample.csv
```
