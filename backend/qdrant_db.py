import os
import json
import numpy as np
from typing import List, Dict, Any, Optional

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


class QdrantVectorStore:
    """
    Qdrant Vector Database integration for high-performance candidate vector search and payload filtering.
    Supports:
      - Qdrant Cloud free tier: Set QDRANT_URL + QDRANT_API_KEY env vars
      - Local disk persistence: Set QDRANT_STORAGE_DIR env var (Docker volume)
      - In-memory mode: fallback when no env vars or storage_dir are set
    """
    def __init__(self, collection_name: str = "candidate_vectors", storage_dir: Optional[str] = None):
        self.collection_name = collection_name
        self.storage_dir = storage_dir
        self.client = None

        if QDRANT_AVAILABLE:
            qdrant_url = os.environ.get("QDRANT_URL", "").strip()
            storage_dir_env = storage_dir or os.environ.get("QDRANT_STORAGE_DIR", "").strip()

            if qdrant_url:
                # Connect to Qdrant Cloud (free tier or paid)
                api_key = os.environ.get("QDRANT_API_KEY", None)
                self.client = QdrantClient(url=qdrant_url, api_key=api_key)
                print(f"Qdrant: Connected to cloud cluster at {qdrant_url}")
            elif storage_dir_env:
                # Local persistent disk storage (Docker volume mount)
                os.makedirs(storage_dir_env, exist_ok=True)
                self.client = QdrantClient(path=storage_dir_env)
                print(f"Qdrant: Using local disk storage at '{storage_dir_env}'")
            else:
                # Fallback: in-memory (lost on restart)
                self.client = QdrantClient(":memory:")
                print("Qdrant: Running in-memory mode (data not persisted)")

    def is_available(self) -> bool:
        return QDRANT_AVAILABLE and self.client is not None

    def init_collection(self, vector_dim: int = 384) -> bool:
        if not self.is_available():
            return False
            
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if self.collection_name not in collections:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE)
                )
            return True
        except Exception as e:
            print(f"Warning: Qdrant collection initialization failed: {e}")
            return False

    def upsert_candidates(self, candidates: List[Dict[str, Any]], embeddings: Optional[np.ndarray] = None) -> bool:
        if not self.is_available() or not candidates:
            return False
            
        try:
            self.init_collection(vector_dim=384)
            points = []
            
            for idx, cand in enumerate(candidates):
                cid = cand.get("candidate_id", f"CAND_{idx:05d}")
                
                if embeddings is not None and idx < len(embeddings):
                    vec = embeddings[idx].tolist()
                else:
                    vec = [0.0] * 384
                    
                profile = cand.get("profile", {})
                signals = cand.get("redrob_signals", {})
                skills = [s.get("name", "") for s in cand.get("skills", []) if s.get("name")]
                
                payload = {
                    "candidate_id": cid,
                    "name": profile.get("anonymized_name", "Unknown"),
                    "title": profile.get("current_title", ""),
                    "company": profile.get("current_company", ""),
                    "yoe": profile.get("years_of_experience", 0),
                    "notice_period": signals.get("notice_period_days", 60),
                    "response_rate": signals.get("recruiter_response_rate", 0.5),
                    "skills": skills
                }
                
                # Numeric point ID for Qdrant Struct
                point_id = abs(hash(cid)) % (2**63 - 1)
                points.append(PointStruct(id=point_id, vector=vec, payload=payload))
                
            self.client.upsert(collection_name=self.collection_name, points=points)
            print(f"Successfully indexed {len(points)} candidates into Qdrant collection '{self.collection_name}'.")
            return True
        except Exception as e:
            print(f"Warning: Failed to index candidates into Qdrant: {e}")
            return False

    def search_candidates(self, query_vector: np.ndarray, top_k: int = 100) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []
            
        try:
            vec = query_vector.tolist() if isinstance(query_vector, np.ndarray) else query_vector
            
            if hasattr(self.client, "query_points"):
                response = self.client.query_points(
                    collection_name=self.collection_name,
                    query=vec,
                    limit=top_k
                )
                results = getattr(response, "points", response)
            else:
                results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=vec,
                    limit=top_k
                )
            
            matches = []
            for hit in results:
                matches.append({
                    "candidate_id": hit.payload.get("candidate_id"),
                    "score": hit.score,
                    "payload": hit.payload
                })
            return matches
        except Exception as e:
            print(f"Warning: Qdrant search failed: {e}")
            return []
