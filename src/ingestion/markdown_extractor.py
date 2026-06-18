import pymupdf4llm

class MarkdownExtractor:
    def __init__(self, page_chunks=False):
        self.page_chunks = page_chunks

    def extract(self, pdf_path: str):
        try:
            markdown = pymupdf4llm.to_markdown(
                pdf_path,
                page_chunks=self.page_chunks
            )
            return markdown
        except Exception as e:
            print(f"Error extracting {pdf_path}: {e}")
            return None
