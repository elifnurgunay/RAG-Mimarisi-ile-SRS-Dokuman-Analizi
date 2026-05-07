# src/infrastructure/pdf_loader.py

from langchain_community.document_loaders import PyPDFLoader


class PDFLoaderService:
    def load(self, pdf_path: str):
        loader = PyPDFLoader(pdf_path)
        return loader.load()