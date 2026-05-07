import re
from typing import Any, List, Dict, Optional
from src.config import REQUIREMENT_ID_PATTERN

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
        req_pattern: str = REQUIREMENT_ID_PATTERN,
        fallback_chunk_size: int = 1000,
        fallback_overlap: int = 200,
    ):
        self.req_pattern = re.compile(req_pattern, re.IGNORECASE)
        self.text_splitter = RecursiveCharacterTextSplitter(
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

    def chunk_document(self, document_text, base_metadata):
        # Metin parçalama işlemini gerçekleştir
        raw_chunks = self.text_splitter.split_text(document_text)
        processed_chunks = []

        for index, chunk_text in enumerate(raw_chunks):
            # PDF'den gelen sayfa numarası vb. metadatayı korumak için kopyala
            chunk_metadata = base_metadata.copy() 
            
            # Genişletilmiş regex ile ID ara
            match = self.req_pattern.search(chunk_text)
            
            if match:
                # Gerçek ID bulunduysa metadata içine kaydet
                chunk_metadata["req_id"] = match.group(1).strip()
            else:
                # ID bulunamazsa Fallback: Sanal ID (AUTO-{sayfa_no}-{sıra_no}) üret
                page_no = chunk_metadata.get("page", "UNKNOWN")
                chunk_metadata["req_id"] = f"AUTO-{page_no}-{index + 1}"

            # Parçayı ve güncellenmiş metadatayı listeye ekle
            processed_chunks.append({
                "text": chunk_text,
                "metadata": chunk_metadata
            })

        return processed_chunks

    def chunk_documents(self, documents: List[Any]) -> List[Any]:
        """Belgeleri REQ-ID tabanlı parçalara ayırır."""
        chunked_documents = []
        for document in documents:
            chunks = self.chunk_document(document.page_content, document.metadata)
            for chunk in chunks:
                chunked_documents.append(self._build_document(chunk["text"], chunk["metadata"]))
        return chunked_documents
