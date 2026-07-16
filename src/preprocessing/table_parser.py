import re


class TableParser:
    """Convert section fragments into ordered text and table blocks."""

    def _is_table_line(self, line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("|") and "|" in stripped[1:]

    def _is_table_caption(self, text: str) -> bool:
        compact = re.sub(r"\s+", " ", text).strip()
        return (
            len(compact) <= 500
            and re.match(r"^(?:table|tab\.)\s*[a-z0-9]+[. :\-]", compact, re.I)
            is not None
        )

    def _is_omitted_media_notice(self, line: str) -> bool:
        return "picture" in line.lower() and "intentionally omitted" in line.lower()

    def _parse_fragment(self, fragment: dict) -> list[dict]:
        blocks = []
        text_lines = []
        table_lines = []
        inside_table = False

        def append_text():
            nonlocal text_lines
            text = "\n".join(text_lines).strip()
            if text:
                for paragraph in re.split(r"\n\s*\n", text):
                    paragraph = paragraph.strip()
                    if paragraph:
                        blocks.append({
                            "block_type": "text",
                            "section": fragment["section"],
                            "page_start": fragment["page_start"],
                            "page_end": fragment["page_end"],
                            "content": paragraph,
                            "caption": None,
                        })
            text_lines = []

        def append_table():
            nonlocal table_lines
            table = "\n".join(table_lines).strip()
            if table:
                caption = None
                if blocks and blocks[-1]["block_type"] == "text":
                    if self._is_table_caption(blocks[-1]["content"]):
                        caption = blocks.pop()["content"]

                blocks.append({
                    "block_type": "table",
                    "section": fragment["section"],
                    "page_start": fragment["page_start"],
                    "page_end": fragment["page_end"],
                    "content": table,
                    "caption": caption,
                })
            table_lines = []

        for line in fragment.get("content", "").splitlines():
            if self._is_omitted_media_notice(line):
                continue

            if self._is_table_line(line):
                if not inside_table:
                    append_text()
                    inside_table = True
                table_lines.append(line)
            else:
                if inside_table:
                    append_table()
                    inside_table = False
                text_lines.append(line)

        if inside_table:
            append_table()
        append_text()
        return blocks

    def parse(self, sections) -> list[dict]:
        if isinstance(sections, dict):
            sections = [
                {
                    "section": section,
                    "page_start": 1,
                    "page_end": 1,
                    "content": content,
                }
                for section, content in sections.items()
            ]

        blocks = []
        for fragment in sections:
            blocks.extend(self._parse_fragment(fragment))
        return blocks
