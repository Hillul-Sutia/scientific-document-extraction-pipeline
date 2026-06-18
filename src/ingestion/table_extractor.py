import pdfplumber

class TableExtractor:
    def extract(self, pdf_path):
        tables = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                extracted_tables = page.extract_tables()

                for table in extracted_tables:
                    tables.append({
                        "page": page_num,
                        "table": table
                    })

        return tables

