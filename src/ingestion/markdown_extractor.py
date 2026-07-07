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

    def extract(self, pdf_path: str):
        try:
            md = pymupdf4llm.to_markdown(
                pdf_path,
                page_chunks=self.page_chunks,
            )
            logger.info(len(md))
            logger.info(md[0].keys())
            
            if not self.page_chunks:
                return md

            if not self.add_page_markers:
                return md

            output = []
            for page in md:
                page_no = page["metadata"]["page_number"]
                output.append(f"<!-- Page {page_no} -->\n")
                output.append(page["text"])
                output.append("\n---\n")

            return "".join(output)

        except Exception as e:
            er_msg = f"Error extracting {pdf_path}: {e}"
            print(er_msg)
            logger.error(er_msg)
            return None