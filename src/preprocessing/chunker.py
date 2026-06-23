class Chunker:
    def chunk(self, parsed_sections: dict) -> list:
        """
        Convert parsed sections into flat chunk list.
        """
        chunks = []

        for section_name, section_data in parsed_sections.items():

            # Process text blocks
            for text_block in section_data.get("text_blocks", []):
                if text_block.strip():
                    chunks.append({
                        "chunk_type": "text",
                        "section": section_name,
                        "content": text_block.strip()
                    })

            # Process tables
            for table in section_data.get("tables", []):
                if table.strip():
                    chunks.append({
                        "chunk_type": "table",
                        "section": section_name,
                        "content": table.strip()
                    })

        return chunks
