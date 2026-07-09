import re

class TableParser:
    # def _is_table_desc(self, line: str) ->:


    def _is_table_line(self, line: str) -> bool:
        """
        Detect markdown-style table lines.

        Example:
        | col1 | col2 |
        """
        return line.startswith("|") and "|" in line[1:]

    def _split_text_blocks(self, text: str):
        """
        Split text into paragraph blocks.
        """
        blocks = re.split(r"\n\s*\n", text)

        return [
            block.strip()
            for block in blocks
            if block.strip()
        ]
    
    # def _is_same_table():

    
    def _parse_section(self, content: str) -> dict:
        """
        Parse one section into:
        {
            text_blocks: [...],
            tables: [...]
        }
        """
        lines = content.split("\n")

        text_lines = []
        tables = []
        current_table = []
        inside_table = False
        table_heading_detected = ''

        for line in lines:
            stripped = line.strip()

            if self._is_table_line(stripped):
                inside_table = True
                current_table.append(line)

            else:
                if inside_table:
                    tables.append("\n".join(current_table))
                    current_table = []
                    inside_table = False

                text_lines.append(line)

        # Save final table if file ends with table
        if current_table:
            tables.append("\n".join(current_table))

        text_blocks = self._split_text_blocks("\n".join(text_lines))

        return {
            "text_blocks": text_blocks,
            "tables": tables
        }
    
    def parse(self, sections: dict) -> dict:
        """
        Parse all sections and separate text blocks and tables.
        """
        parsed_sections = {}

        for section_name, content in sections.items():
            parsed_sections[section_name] = self._parse_section(content)

        return parsed_sections

