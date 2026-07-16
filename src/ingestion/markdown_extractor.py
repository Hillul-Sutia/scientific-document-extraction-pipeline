import pymupdf4llm
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# class MarkdownExtractor:
#     def __init__(self, page_chunks=False):
#         self.page_chunks = page_chunks

#     def extract(self, pdf_path: str):
#         try:
#             markdown = pymupdf4llm.to_markdown(
#                 pdf_path,
#                 page_chunks=self.page_chunks
#             )
#             return markdown
#         except Exception as e:
#             print(f"Error extracting {pdf_path}: {e}")
#             return None


class MarkdownExtractor:
    def __init__(self, page_chunks=True, add_page_markers=True):
        self.page_chunks = page_chunks
        self.add_page_markers = add_page_markers

    def extract_pages(self, pdf_path: str) -> list[dict]:
        """Extract a PDF as ordered, page-aware records."""
        try:
            extracted_pages = pymupdf4llm.to_markdown(
                pdf_path,
                page_chunks=True,
            )
            pages = []

            for page_index, page in enumerate(extracted_pages, start=1):
                metadata = page.get("metadata", {})
                page_number = metadata.get("page_number", page_index)
                pages.append({
                    "page_number": int(page_number),
                    "content": page.get("text", ""),
                })

            logger.info("Extracted %s pages from %s", len(pages), pdf_path)
            return pages

        except Exception as e:
            er_msg = f"Error extracting {pdf_path}: {e}"
            logger.exception(er_msg)
            raise

    def render_markdown(self, pages: list[dict]) -> str:
        """Render page records as a human-readable Markdown artifact."""
        output = []
        for page in pages:
            if self.add_page_markers:
                output.append(f"<!-- Page {page['page_number']} -->\n")
            output.append(page["content"])
            output.append("\n---\n")
        return "".join(output)

    def extract(self, pdf_path: str):
        """Backward-compatible Markdown extraction entry point."""
        pages = self.extract_pages(pdf_path)
        if self.page_chunks:
            return self.render_markdown(pages)
        return "\n".join(page["content"] for page in pages)
