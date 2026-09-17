from pypdf import PdfReader
from io import BytesIO

class DocumentParser:
    @staticmethod
    def parse_pdf(file_bytes: bytes, chunk_size: int = 500, overlap: int = 50) -> list[dict]:
        reader = PdfReader(BytesIO(file_bytes))
        chunks = []
        
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            words = text.split()
            
            for i in range(0, len(words), chunk_size - overlap):
                chunk_text = " ".join(words[i:i + chunk_size])
                if chunk_text.strip():
                    chunks.append({
                        "page": page_num + 1,
                        "content": chunk_text
                    })
        return chunks

doc_parser = DocumentParser()