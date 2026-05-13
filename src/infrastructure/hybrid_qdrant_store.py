import uuid
import math
import re
from typing import Any, List

from langchain_core.documents import Document
from qdrant_client import QdrantClient, models

from src.config import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME
from src.infrastructure.embedding_service import EmbeddingService
from src.infrastructure.sparse_embedding_service import SparseEmbeddingService
from src.utils.logging_utils import get_logger


logger = get_logger(__name__)


def _is_invalid_text_value(value: Any) -> bool:
    if value is None:
        return True

    try:
        if isinstance(value, float) and math.isnan(value):
            return True
    except Exception:
        pass

    return False


_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")

def _clean_surrogates(text: str) -> str:
    if not isinstance(text, str):
        text = str(text)

    # Surrogate karakterleri sil
    text = _SURROGATE_RE.sub("", text)

    # UTF-8 encode/decode ile kalan bozuk karakterleri temizle
    text = text.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")

    # Null ve kontrol karakterlerini temizle
    text = text.replace("\x00", " ")
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", " ", text)

    # Whitespace normalize et
    text = re.sub(r"\s+", " ", text).strip()

    return text


def _make_json_safe(value: Any) -> Any:
    """
    Qdrant payload JSON serialization için güvenli hale getirir.
    Tüm stringlerde invalid surrogate ve kontrol karakterlerini temizler.
    Dict/list içinde recursive çalışır.
    """
    if value is None:
        return None

    if isinstance(value, str):
        return _clean_surrogates(value)

    if isinstance(value, bytes):
        return _clean_surrogates(value.decode("utf-8", errors="ignore"))

    if isinstance(value, (int, float, bool)):
        return value

    if isinstance(value, dict):
        safe_dict = {}
        for k, v in value.items():
            safe_key = _clean_surrogates(str(k))
            safe_dict[safe_key] = _make_json_safe(v)
        return safe_dict

    if isinstance(value, (list, tuple, set)):
        return [_make_json_safe(item) for item in value]

    return _clean_surrogates(str(value))


def _to_safe_text(value: Any) -> str:
    if _is_invalid_text_value(value):
        return ""

    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")

    text = _clean_surrogates(str(value))

    if text.lower() in {"none", "nan", "null", "<na>"}:
        return ""

    return text


def _sanitize_documents_for_embedding(documents):
    """
    documents listesini temizler.
    texts ve clean_docs birebir senkron döner.
    """
    clean_docs = []
    clean_texts = []

    for i, doc in enumerate(documents or []):
        raw = getattr(doc, "page_content", None)
        text = _to_safe_text(raw)

        if not text:
            logger.warning(
                "Embedding için geçersiz chunk atlandı | index=%d | raw_type=%s | raw_repr=%s",
                i,
                type(raw).__name__,
                repr(raw)[:200],
            )
            continue

        # doc.page_content kesin string olsun
        doc.page_content = text

        clean_docs.append(doc)
        clean_texts.append(text)

    return clean_docs, clean_texts


def _assert_texts_are_safe(texts: List[str]) -> None:
    bad_items = []

    for i, item in enumerate(texts):
        if type(item) is not str:
            bad_items.append((i, type(item).__name__, repr(item)[:300]))
            continue

        if not item.strip():
            bad_items.append((i, "empty_str", repr(item)[:300]))

    if bad_items:
        logger.error("Embedding öncesi geçersiz text öğeleri bulundu: %s", bad_items[:20])
        raise TypeError(f"Unsafe embedding texts: {bad_items[:20]}")


def _safe_embed_documents(embedding_model, texts: List[str]) -> tuple[List[List[float]], List[int]]:
    """
    LangChain HuggingFaceEmbeddings.embed_documents batch çağrısı tokenizer hatası verirse,
    hatalı öğeyi bulmak ve sistemi kurtarmak için tek tek embed_query fallback kullanır.
    """
    _assert_texts_are_safe(texts)

    # Önce hızlı batch dene
    try:
        vectors = embedding_model.embed_documents(list(texts))
        return vectors, list(range(len(texts)))
    except TypeError as exc:
        logger.warning(
            "Batch embed_documents TypeError verdi. Tek tek embed_query fallback kullanılacak | hata=%s",
            exc,
        )

    vectors = []
    kept_indices = []

    logger.info(
        "Fallback: toplam text=%d | ilk 3 type=%s | ilk 3 preview=%s",
        len(texts),
        [type(t).__name__ for t in texts[:3]],
        [repr(str(t)[:100]) for t in texts[:3]],
    )

    for i, text in enumerate(texts):
        try:
            safe_text = str(text)
            safe_text = safe_text.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
            safe_text = safe_text.replace("\x00", " ")
            safe_text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", " ", safe_text)
            safe_text = re.sub(r"\s+", " ", safe_text).strip()

            if not safe_text or safe_text.lower() in {"none", "nan", "null", "<na>"}:
                logger.warning(
                    "Tekil embedding için geçersiz metin atlandı | index=%d | preview=%s",
                    i,
                    repr(str(text)[:300]),
                )
                continue

            if type(safe_text) is not str:
                logger.warning(
                    "Tekil embedding öncesi text hâlâ str değil, atlandı | index=%d | type=%s",
                    i,
                    type(safe_text).__name__,
                )
                continue

            vector = embedding_model.embed_query(safe_text)

            vectors.append(vector)
            kept_indices.append(i)

        except Exception as item_exc:
            logger.error(
                "Chunk embedding başarısız olduğu için atlandı | index=%d | type=%s | preview=%s | hata=%s",
                i,
                type(text).__name__,
                repr(str(text)[:500]),
                item_exc,
            )
            continue

    if not vectors:
        raise RuntimeError(
            "Hiçbir chunk embed edilemedi. Embedding modeli veya input temizleme aşaması kontrol edilmeli."
        )

    skipped = [i for i in range(len(texts)) if i not in kept_indices]

    logger.warning(
        "Tekil embedding fallback tamamlandı | başarılı=%d | atlanan=%d | skipped_indices=%s",
        len(vectors),
        len(texts) - len(vectors),
        skipped[:20],
    )

    return vectors, kept_indices


def _deduplicate_sparse_vector(indices, values):
    merged = {}

    for idx, val in zip(indices or [], values or []):
        if idx is None:
            continue

        idx = int(idx)
        val = float(val)

        if idx in merged:
            merged[idx] += val
        else:
            merged[idx] = val

    sorted_items = sorted(merged.items())

    dedup_indices = [idx for idx, _ in sorted_items]
    dedup_values = [val for _, val in sorted_items]

    return dedup_indices, dedup_values


def _normalize_sparse_vector(vector):
    if vector is None:
        return None

    if isinstance(vector, models.SparseVector):
        indices, values = _deduplicate_sparse_vector(vector.indices, vector.values)
        if not indices:
            return None
        return models.SparseVector(indices=indices, values=values)

    if isinstance(vector, dict):
        indices, values = _deduplicate_sparse_vector(
            vector.get("indices", []),
            vector.get("values", []),
        )
        if not indices:
            return None
        return {"indices": indices, "values": values}

    return vector


class HybridQdrantStore:
    def __init__(
        self,
        collection_name: str = QDRANT_COLLECTION_NAME,
        dense_vector_name: str = "dense",
        sparse_vector_name: str = "sparse",
    ):
        self.collection_name = collection_name
        self.dense_vector_name = dense_vector_name
        self.sparse_vector_name = sparse_vector_name

        self.client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            timeout=60.0,
        )

        self.embedding_service = EmbeddingService()
        self.dense_embeddings = self.embedding_service.get_embeddings()
        self.sparse_embeddings = SparseEmbeddingService()

    def recreate_collection(self, vector_size: int) -> None:
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config={
                self.dense_vector_name: models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                self.sparse_vector_name: models.SparseVectorParams()
            },
        )

    def add_documents(self, documents: List[Document], force_recreate: bool = True):
        if not documents:
            return

        valid_documents, texts = _sanitize_documents_for_embedding(documents)

        if not texts:
            logger.warning("Embedding için geçerli metin bulunamadı.")
            return False

        logger.info(
            "Embedding input hazır | doc_count=%d | text_count=%d | first_type=%s | first_preview=%s",
            len(valid_documents),
            len(texts),
            type(texts[0]).__name__,
            repr(texts[0][:200]),
        )

        dense_vectors, kept_indices = _safe_embed_documents(self.dense_embeddings, texts)

        valid_documents = [valid_documents[i] for i in kept_indices]
        texts = [texts[i] for i in kept_indices]

        sparse_vectors = [self.sparse_embeddings.encode(text) for text in texts]

        if len(dense_vectors) != len(valid_documents):
            raise RuntimeError(
                f"Dense vector/document count mismatch: vectors={len(dense_vectors)}, docs={len(valid_documents)}"
            )

        vector_size = len(dense_vectors[0])

        if force_recreate:
            self.recreate_collection(vector_size=vector_size)

        points = []

        for doc, dense_vector, sparse_vector in zip(valid_documents, dense_vectors, sparse_vectors):
            norm_sparse = _normalize_sparse_vector(sparse_vector)
            
            vector_dict = {
                self.dense_vector_name: dense_vector,
            }
            if norm_sparse is not None:
                vector_dict[self.sparse_vector_name] = norm_sparse

            point_id = str(uuid.uuid4())
            
            meta = getattr(doc, "metadata", {}) or {}
            safe_payload = _make_json_safe({
                "page_content": getattr(doc, "page_content", ""),
                "_chunk_index": meta.get("chunk_index", 0),
                "_metadata": meta,
            })
            
            try:
                import json
                json.dumps(safe_payload, ensure_ascii=False)
            except UnicodeEncodeError as exc:
                logger.error("Payload hâlâ JSON-safe değil | point=%s | hata=%s | payload_preview=%s", point_id, exc, repr(safe_payload)[:500])
                safe_payload = json.loads(json.dumps(safe_payload, ensure_ascii=True, errors="ignore"))

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector_dict,
                    payload=safe_payload,
                )
            )

        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            logger.info("Qdrant indexleme tamamlandı. %d adet chunk eklendi.", len(points))
        except Exception as exc:
            err_msg = str(exc)
            if "422" in err_msg or "Unprocessable Entity" in err_msg:
                logger.error("Qdrant upsert 422 Hatası: Sparse vector doğrulama başarısız oldu (duplicate indices vb).")
                for i, p in enumerate(points):
                    logger.debug("Point %d Sparse: %s", i, p.vector.get(self.sparse_vector_name))
                raise RuntimeError("İndeksleme sırasında sparse vector doğrulama hatası (422) oluştu.") from exc
            else:
                logger.error("Qdrant upsert hatası: %s", exc)
                raise

    def hybrid_search(self, query: str, top_k: int = 5) -> List[Document]:
        dense_query = self.dense_embeddings.embed_query(query)
        sparse_query = self.sparse_embeddings.encode(query)

        response = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_query,
                    using=self.dense_vector_name,
                    limit=top_k * 4,
                ),
                models.Prefetch(
                    query=sparse_query,
                    using=self.sparse_vector_name,
                    limit=top_k * 4,
                ),
            ],
            query=models.FusionQuery(
                fusion=models.Fusion.RRF,
            ),
            limit=top_k,
            with_payload=True,
        )

        docs: List[Document] = []

        for point in response.points:
            payload = point.payload or {}
            metadata = payload.get("metadata", {})
            metadata["qdrant_score"] = float(point.score)

            docs.append(
                Document(
                    page_content=payload.get("page_content", ""),
                    metadata=metadata,
                )
            )

        return docs

    def scroll_all_documents(self, limit: int = 100) -> List[Document]:
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            limit=limit,
            with_payload=True,
        )

        docs = []

        for point in points:
            payload = point.payload or {}
            # Metadata is stored under _metadata key
            meta = payload.get("_metadata", {})
            # Fallback: if old format (no _metadata key), use empty dict
            if not meta:
                meta = {}
            meta["chunk_index"] = payload.get("_chunk_index", 0)
            docs.append(
                Document(
                    page_content=payload.get("page_content", ""),
                    metadata=meta,
                )
            )

        # Sort by chunk_index to guarantee deterministic ordering
        docs.sort(key=lambda d: d.metadata.get("chunk_index", 0))
        return docs