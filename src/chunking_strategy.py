import re
from typing import Any, List, Dict, Optional

try:
    from langchain_core.documents import Document
except ImportError:
    try:
        from langchain.schema import Document
    except ImportError:
        Document = None  # type: ignore

from langchain_text_splitters import RecursiveCharacterTextSplitter


class ReqChunkingStrategy:
    """REQ-ID bazlı chunking stratejisi.

    Bu strateji, PDF metnini REQ-xxx girdilerine göre parçalar.
    Eğer bir sayfada REQ-ID bulunmazsa, sayfayı yine de anlamlı parçalara
    bölen varsayılan bir metin ayırıcıya (fallback) döner.
    """

    def __init__(
        self,
        req_pattern: str = r"(REQ-\d{3,})",
        fallback_chunk_size: int = 1000,
        fallback_overlap: int = 200,
    ):
        self.req_pattern = re.compile(req_pattern, re.IGNORECASE)
        self.fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=fallback_chunk_size,
            chunk_overlap=fallback_overlap,
        )

    def chunk_text(self, text: str) -> List[Dict[str, str]]:
        """Metni REQ-ID bloklarına ayırır."""
        if not text or not text.strip():
            return []

        matches = list(self.req_pattern.finditer(text))
        if not matches:
            return []

        chunks = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            block = text[start:end].strip()
            req_id = match.group(1).upper()
            chunks.append({
                "Requirement_ID": req_id,
                "Content": block,
            })

        return chunks

    def _build_document(self, page_content: str, metadata: Dict[str, Any]) -> Any:
        if Document is not None:
            return Document(page_content=page_content, metadata=metadata)
        return {"page_content": page_content, "metadata": metadata}

    def chunk_document(self, document: Any) -> List[Any]:
        """Tek bir dokümanı REQ-ID bazında chunk'lar veya fallback yapar."""
        req_chunks = self.chunk_text(document.page_content)
        if not req_chunks:
            return self.fallback_splitter.split_documents([document])

        chunk_docs = []
        for index, req_chunk in enumerate(req_chunks):
            metadata = dict(getattr(document, "metadata", {}) or {})
            metadata.update(
                {
                    "req_id": req_chunk["Requirement_ID"],
                    "chunk_index": index,
                }
            )
            chunk_docs.append(
                self._build_document(
                    page_content=req_chunk["Content"],
                    metadata=metadata,
                )
            )

        return chunk_docs

    def chunk_documents(self, documents: List[Any]) -> List[Any]:
        """Belgeleri REQ-ID tabanlı parçalara ayırır."""
        chunked_documents = []
        for document in documents:
            chunked_documents.extend(self.chunk_document(document))

        return chunked_documents
