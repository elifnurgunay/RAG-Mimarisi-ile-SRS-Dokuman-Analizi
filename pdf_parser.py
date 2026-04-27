import fitz  # PyMuPDF kütüphanesi bu isimle içe aktarılır
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class PDFParserError(Exception):
    pass


class PDFParser:
    def __init__(self, file_path: str, req_pattern: str = r"(REQ-\d{3,})"):
        self.file_path = Path(file_path)
        self.req_pattern = re.compile(req_pattern, re.IGNORECASE)

    def _validate_file(self) -> None:
        if not self.file_path.exists():
            raise PDFParserError(f"Dosya bulunamadı: {self.file_path}")
        if not self.file_path.is_file():
            raise PDFParserError(f"Geçerli bir dosya değil: {self.file_path}")

    def extract_text(self) -> Optional[str]:
        """PDF'teki tüm metni düz metin olarak çıkarır."""
        try:
            self._validate_file()
            pages_text: List[str] = []
            with fitz.open(self.file_path) as doc:
                for page_number, page in enumerate(doc, start=1):
                    pages_text.append(page.get_text("text") or "")
            return "\n".join(pages_text)
        except Exception as exc:
            print(f"[ERROR] PDF metin çıkarma hatası: {exc}")
            return None

    def extract_pages(self) -> List[Dict[str, Any]]:
        """Her sayfa için metin ve tablo bilgilerini çıkarır."""
        pages: List[Dict[str, Any]] = []

        try:
            self._validate_file()
            with fitz.open(self.file_path) as doc:
                for page_number, page in enumerate(doc, start=1):
                    text = page.get_text("text") or ""
                    tables = self._extract_tables_from_page(page)
                    pages.append(
                        {
                            "page": page_number,
                            "text": text,
                            "tables": tables,
                        }
                    )
        except Exception as exc:
            print(f"[ERROR] PDF sayfa çıkarma hatası: {exc}")
        return pages

    def _extract_tables_from_page(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """Sayfa içerisinden tablo benzeri blokları tespit eder."""
        try:
            page_dict = page.get_text("dict")
            tables: List[Dict[str, Any]] = []

            for block in page_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue

                rows = []
                for line in block.get("lines", []):
                    spans = [span for span in line.get("spans", []) if span.get("text", "").strip()]
                    if not spans:
                        continue
                    cells = [self._normalize_text(span["text"]) for span in spans]
                    rows.append({
                        "y": line["bbox"][1],
                        "x_positions": [span["bbox"][0] for span in spans],
                        "cells": cells,
                    })

                if len(rows) < 2:
                    continue

                multi_cell_lines = sum(1 for row in rows if len(row["cells"]) > 1)
                if multi_cell_lines / len(rows) < 0.6:
                    continue

                table_rows = [row["cells"] for row in rows]
                if not table_rows:
                    continue

                tables.append(
                    {
                        "row_count": len(table_rows),
                        "column_count": max(len(row) for row in table_rows),
                        "rows": [self._pad_row(row, max(len(r) for r in table_rows)) for row in table_rows],
                    }
                )

            return tables
        except Exception as exc:
            print(f"[ERROR] Tablo çıkarma hatası: {exc}")
            return []

    def _normalize_text(self, text: str) -> str:
        return text.replace("\n", " ").strip()

    def _pad_row(self, row: List[str], width: int) -> List[str]:
        return row + [""] * (width - len(row))

    def parse_requirements(self, text: Optional[str] = None) -> List[Dict[str, Any]]:
        """Metni REQ-ID bloklarına ayırır."""
        if text is None:
            text = self.extract_text() or ""

        if not text.strip():
            return []

        matches = list(self.req_pattern.finditer(text))
        if not matches:
            return []

        requirements: List[Dict[str, Any]] = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            block = text[start:end].strip()
            req_id = match.group(1).upper()
            requirements.append({
                "Requirement_ID": req_id,
                "text": block,
            })

        return requirements

    def parse_pdf(self) -> Dict[str, Any]:
        """PDF'i tam yapılandırılmış biçimde döndürür."""
        pages = self.extract_pages()
        all_text = "\n".join(page["text"] for page in pages)
        requirements = self.parse_requirements(all_text)
        return {
            "file_path": str(self.file_path),
            "page_count": len(pages),
            "pages": pages,
            "requirements": requirements,
        }


if __name__ == "__main__":
    parser = PDFParser("ornek_srs.pdf")

    parsed = parser.parse_pdf()
    print(f"Sayfa sayısı: {parsed['page_count']}")
    print(f"Bulan gereksinim sayısı: {len(parsed['requirements'])}")

    for requirement in parsed["requirements"]:
        print(f"{requirement['Requirement_ID']}: {requirement['text'][:120]}...\n")

    for page in parsed["pages"]:
        if page["tables"]:
            print(f"Sayfa {page['page']} içinde {len(page['tables'])} tablo bulundu:")
            for table in page["tables"]:
                print(table)
