import os
import re
from typing import List, Dict

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_TORCH", "1")

from sentence_transformers import SentenceTransformer
import chromadb

MODULE_NAME = "all-MiniLM-L6-v2"
_MODEL: "SentenceTransformer | None" = None


def _get_model() -> "SentenceTransformer":
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(MODULE_NAME)
    return _MODEL


def _build_collection_name(company: str, filing_type: str) -> str:
    name = company.lower()
    name = re.sub(r"[\s\-]+", "_", name)
    name = re.sub(r"[^a-z0-9_]", "", name)
    ftype = filing_type.lower()
    ftype = re.sub(r"[^a-z0-9]", "", ftype)
    return f"{name}_{ftype}"


def ingest_chunks(chunks: List[Dict], filing_meta: Dict) -> Dict:
    try:
        collection_name = _build_collection_name(
            filing_meta.get("company", "unknown"),
            filing_meta.get("filing_type", "10k"),
        )

        if not chunks:
            return {"chunks_inserted": 0, "collection_name": collection_name, "status": "ok"}

        persist_dir = os.environ.get("CHROMA_PERSIST_DIR", ".chroma")
        client = chromadb.PersistentClient(path=persist_dir)
        collection = client.get_or_create_collection(name=collection_name)

        ids = [f"{filing_meta['accession_number']}_{c['chunk_id']}" for c in chunks]
        texts = [c["content"] for c in chunks]
        embeddings = _get_model().encode(texts).tolist()
        metadatas = [
            {
                "company": filing_meta.get("company", ""),
                "filing_date": filing_meta.get("filing_date", ""),
                "filing_type": filing_meta.get("filing_type", ""),
                "chunk_id": c["chunk_id"],
                "section_name": c["section_name"],
            }
            for c in chunks
        ]

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        return {"chunks_inserted": len(chunks), "collection_name": collection_name, "status": "ok"}
    except Exception:
        return {"chunks_inserted": 0, "collection_name": None, "status": "error"}
