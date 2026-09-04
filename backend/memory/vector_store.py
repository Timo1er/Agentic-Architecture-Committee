import logging
import hashlib
import json
from typing import List, Dict, Any, Optional
from backend.config import settings

logger = logging.getLogger("arb.memory")

class VectorMemoryService:
    """Service to index human feedback, ADR decisions, and architectural corrections into vector memory."""

    def __init__(self):
        self.collection_name = settings.QDRANT_COLLECTION
        self.vector_size = 384 # Standard size for all-MiniLM-L6-v2 or deterministic hashing
        self._in_memory_docs: List[Dict[str, Any]] = []
        self._qdrant_client = None
        self._encoder = None
        self._init_client()

    def _init_client(self):
        if settings.VECTOR_DB_TYPE == "qdrant":
            try:
                from qdrant_client import QdrantClient
                from qdrant_client.http import models as qmodels
                
                # Connect to Qdrant host or fallback to local in-memory
                try:
                    self._qdrant_client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, timeout=2.0)
                    # Check connection
                    self._qdrant_client.get_collections()
                    # Ensure collection exists
                    collections = [c.name for c in self._qdrant_client.get_collections().collections]
                    if self.collection_name not in collections:
                        self._qdrant_client.create_collection(
                            collection_name=self.collection_name,
                            vectors_config=qmodels.VectorParams(size=self.vector_size, distance=qmodels.Distance.COSINE)
                        )
                    logger.info("Connected successfully to Qdrant server.")
                except Exception as e:
                    logger.info(f"Qdrant server not reachable ({e}). Initializing in-memory fallback vector store.")
                    self._qdrant_client = QdrantClient(":memory:")
                    self._qdrant_client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=qmodels.VectorParams(size=self.vector_size, distance=qmodels.Distance.COSINE)
                    )
            except Exception as e:
                logger.warning(f"Could not initialize QdrantClient: {e}. Using internal list store.")
                self._qdrant_client = None

    def _get_embedding(self, text: str) -> List[float]:
        """Compute vector embedding using deterministic semantic projection or SentenceTransformers if enabled."""
        import os
        if os.getenv("USE_SENTENCE_TRANSFORMERS", "false").lower() == "true":
            if not self._encoder:
                try:
                    from sentence_transformers import SentenceTransformer
                    self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
                except Exception:
                    self._encoder = "fallback"

            if self._encoder and self._encoder != "fallback":
                try:
                    embedding = self._encoder.encode(text).tolist()
                    return embedding
                except Exception:
                    pass

        # Deterministic semantic hash projection (ensures reproducible vectors without heavy models)
        vector = [0.0] * self.vector_size
        words = text.lower().split()
        for idx, word in enumerate(words):
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            pos = h % self.vector_size
            vector[pos] += 1.0 / (idx + 1)
        
        # Normalize vector
        norm = sum(x * x for x in vector) ** 0.5
        if norm > 0:
            vector = [x / norm for x in vector]
        return vector

    def index_feedback(
        self,
        feedback_id: str,
        review_id: str,
        title: str,
        verdict: str,
        rating: int,
        comments: Optional[str] = None,
        corrections: Optional[str] = None,
        target_clouds: Optional[List[str]] = None,
        context: Optional[str] = None
    ) -> bool:
        """Store operator feedback and architectural lessons learned."""
        text_content = f"Title: {title}\nVerdict: {verdict}\nRating: {rating} stars\nClouds: {target_clouds}\nComments: {comments or ''}\nCorrections: {corrections or ''}\nContext: {context or ''}"
        vector = self._get_embedding(text_content)
        payload = {
            "feedback_id": feedback_id,
            "review_id": review_id,
            "title": title,
            "verdict": verdict,
            "rating": rating,
            "comments": comments or "",
            "corrections": corrections or "",
            "target_clouds": target_clouds or [],
            "content": text_content
        }

        # Always maintain in-memory docs for resilient fallback & standalone test execution
        self._in_memory_docs.append({"vector": vector, "payload": payload})

        if self._qdrant_client:
            try:
                from qdrant_client.http import models as qmodels
                point_id = int(hashlib.md5(feedback_id.encode()).hexdigest()[:8], 16)
                self._qdrant_client.upsert(
                    collection_name=self.collection_name,
                    points=[
                        qmodels.PointStruct(
                            id=point_id,
                            vector=vector,
                            payload=payload
                        )
                    ]
                )
                logger.info(f"Feedback {feedback_id} successfully indexed into Qdrant.")
            except Exception as e:
                logger.warning(f"Error upserting to Qdrant: {e}")

        return True

    def search_relevant_feedback(self, query_text: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Retrieve most similar historical reviews & corrections to guide agent decisions."""
        vector = self._get_embedding(query_text)
        results = []

        if self._qdrant_client:
            try:
                if hasattr(self._qdrant_client, "search"):
                    hits = self._qdrant_client.search(
                        collection_name=self.collection_name,
                        query_vector=vector,
                        limit=limit
                    )
                    for hit in hits:
                        results.append({
                            "score": hit.score,
                            "payload": hit.payload
                        })
                    if results:
                        return results
                elif hasattr(self._qdrant_client, "query_points"):
                    res = self._qdrant_client.query_points(
                        collection_name=self.collection_name,
                        query=vector,
                        limit=limit
                    )
                    points = getattr(res, "points", res)
                    for p in points:
                        results.append({
                            "score": getattr(p, "score", 1.0),
                            "payload": getattr(p, "payload", {})
                        })
                    if results:
                        return results
            except Exception as e:
                logger.warning(f"Qdrant query fallback: {e}")

        # In-memory cosine similarity fallback
        scored = []
        for doc in self._in_memory_docs:
            doc_vec = doc["vector"]
            dot_prod = sum(a * b for a, b in zip(vector, doc_vec))
            scored.append((dot_prod, doc["payload"]))

        scored.sort(key=lambda x: x[0], reverse=True)
        for score, payload in scored[:limit]:
            results.append({"score": score, "payload": payload})

        return results

    def format_memory_context(self, query_text: str) -> str:
        """Format retrieved lessons into a prompt context block."""
        results = self.search_relevant_feedback(query_text, limit=3)
        if not results:
            return "No historical human corrections found for this topology."

        formatted = ["### Historical Architectural Lessons & Human Corrections:"]
        for idx, item in enumerate(results, 1):
            p = item["payload"]
            formatted.append(f"{idx}. Architecture: {p.get('title')} (Verdict: {p.get('verdict')}, Rating: {p.get('rating')}/5)")
            if p.get("corrections"):
                formatted.append(f"   - Human Correction: {p.get('corrections')}")
            if p.get("comments"):
                formatted.append(f"   - Reviewer Remarks: {p.get('comments')}")
        return "\n".join(formatted)

vector_memory = VectorMemoryService()
