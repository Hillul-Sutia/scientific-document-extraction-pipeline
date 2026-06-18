from pathlib import Path

class PDFLoader:
    def __init__(self, pdf_dir: str):
        self.pdf_dir = Path(pdf_dir)

    
    def get_pdf_files(self):
        return list(self.pdf_dir.glob("*.pdf"))
    
