# imports
from sentence_transformers import SentenceTransformer
import chromadb
from pathlib import Path
import numpy as np

# ── Constants ─────────────────────────────────────────────────────────────────
KNOWLEDGE_BASE_PATH = Path("./knowledge")
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "openbmc_docs"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# ── Module-level singletons (loaded once, reused forever) ─────────────────────
_model: SentenceTransformer | None = None
_collection = None


def _get_model() -> SentenceTransformer:
    """Lazy-load the embedding model once per process."""
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL_NAME)
    return _model


def _get_collection():
    """
    Return the ChromaDB collection.
    Opens the persistent DB — never re-indexes.
    Call build_index() separately to populate it.
    """
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection = client.get_or_create_collection(name=COLLECTION_NAME)
    return _collection


# ── Indexing (run once, or when knowledge base changes) ───────────────────────


def _chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """
    Split text into overlapping character-level chunks.
    Overlap preserves context at chunk boundaries.
    e.g. chunk_size=500, overlap=50 → chunks at [0:500], [450:950], [900:1400]…
    """
    chunks, start = [], 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def build_index(force: bool = False) -> None:
    """
    Read all .txt files from the knowledge folder, chunk them,
    embed with SentenceTransformer, and store in ChromaDB.

    Args:
        force: If True, drop and rebuild the collection from scratch.
               Use this when knowledge base files have changed.

    Safe to call multiple times — skips re-indexing by default.
    """
    collection = _get_collection()

    # Skip if already indexed and force=False
    if not force and collection.count() > 0:
        print(
            f"[RAG] Index already contains {collection.count()} chunks. "
            "Pass force=True to rebuild."
        )
        return

    if force:
        # Wipe and recreate the collection cleanly
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        client.delete_collection(name=COLLECTION_NAME)
        global _collection
        _collection = client.get_or_create_collection(name=COLLECTION_NAME)
        collection = _collection

    # Chunk all .txt files
    all_chunks, all_ids, metadatas = [], [], []
    for file in KNOWLEDGE_BASE_PATH.glob("*.txt"):
        text = file.read_text(encoding="utf-8", errors="ignore")
        for idx, chunk in enumerate(_chunk_text(text)):
            all_chunks.append(chunk)
            all_ids.append(f"{file.stem}_{idx}")
            metadatas.append({"source": file.stem, "chunk_index": idx})

    if not all_chunks:
        raise ValueError(f"No .txt files found in {KNOWLEDGE_BASE_PATH}")

    # Embed and store
    model = _get_model()
    embeddings = model.encode(
        all_chunks, batch_size=32, show_progress_bar=True
    ).tolist()

    collection.add(
        documents=all_chunks, embeddings=embeddings, ids=all_ids, metadatas=metadatas
    )
    print(f"[RAG] Indexed {len(all_chunks)} chunks from {KNOWLEDGE_BASE_PATH}")


# ── Retrieval ─────────────────────────────────────────────────────────────────


def _best_sentence(query: str, chunk: str) -> str:
    """
    Cosine re-rank at sentence level.
    Splits on both '.' and newlines, then picks the sentence
    most semantically similar to the query.
    """
    # Split on newlines first, then on periods — gives cleaner sentences
    raw_lines = chunk.replace("\n", "|").replace(".", ".|").split("|")
    sentences = [s.strip() for s in raw_lines if s.strip()]

    if not sentences:
        return chunk

    if len(sentences) == 1:
        return sentences[0]

    model = _get_model()
    q_emb = model.encode([query])
    s_emb = model.encode(sentences)

    q_norm = q_emb / np.linalg.norm(q_emb, axis=1, keepdims=True)
    s_norm = s_emb / np.linalg.norm(s_emb, axis=1, keepdims=True)
    scores = (q_norm @ s_norm.T).flatten()

    # Debug — remove after confirming correct output
    for s, sc in zip(sentences, scores):
        print(f"  {sc:.4f}  {s}")

    return sentences[int(np.argmax(scores))]


# this is retreving the sentence with the exact words matched higher - to change this I can add a
# penalty for exact word matches and boost sentences that have similar meaning but different words. I can do this
# by adding a small constant to the scores of sentences that have a high cosine similarity but
# do not have exact word matches with the query. This way, sentences that are semantically similar
# but do not have exact word matches will be ranked higher than sentences that have exact word matches
#  are not semantically similar.

_rag_cache: dict[tuple[str, int], str] = {}


def rag_query(query: str, n_chunks: int = 1) -> str:
    """
    Main RAG entry point.

    Args:
        query   : natural language question  e.g. "Memory ECC error"
        n_chunks: how many top chunks to retrieve before sentence re-ranking
                  (default 1 is enough for focused answers)

    Returns:
        The single most relevant sentence from the knowledge base.

    Example:
        >>> rag_query("Memory ECC error")
        'Repeated ECC errors often indicate DIMM degradation.'
    """
    cache_key = (query, n_chunks)
    if cache_key in _rag_cache:
        return _rag_cache[cache_key]

    collection = _get_collection()
    if collection.count() == 0:
        raise RuntimeError("Index is empty. Run build_index() first.")

    results = collection.query(query_texts=[query], n_results=n_chunks)
    top_chunk = results["documents"][0][0]
    res = _best_sentence(query, top_chunk)

    _rag_cache[cache_key] = res
    return res


def search_knowledge_base(query: str, n_results: int = 1) -> dict:
    """
    Backwards-compatible wrapper — returns the raw ChromaDB result dict,
    same shape as your original function.
    Kept so nothing else in your codebase breaks.
    """
    collection = _get_collection()
    return collection.query(query_texts=[query], n_results=n_results)


if __name__ == "__main__":
    # Example usage
    build_index(force=True)  # Build the index from knowledge base files
    answer = rag_query("Memory ECC error")
    print(f"Answer: {answer}")
