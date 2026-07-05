import os
from typing import List, Dict

import chromadb


def retrieve_chunks(question: str, collection_name: str, n_results: int = 5) -> List[Dict]:
    try:
        from data.vector_store import _get_model
        persist_dir = os.environ.get("CHROMA_PERSIST_DIR", ".chroma")
        client = chromadb.PersistentClient(path=persist_dir)
        collection = client.get_collection(name=collection_name)

        question_embedding = _get_model().encode([question])[0].tolist()

        result = collection.query(
            query_embeddings=[question_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]

        chunks = []
        for content, meta, dist in zip(documents, metadatas, distances):
            chunks.append({
                "content": content,
                "section_name": meta.get("section_name", ""),
                "company": meta.get("company", ""),
                "filing_date": meta.get("filing_date", ""),
                "filing_type": meta.get("filing_type", ""),
                "chunk_id": meta.get("chunk_id"),
                "score": float(dist),
            })

        return chunks
    except Exception:
        return []
