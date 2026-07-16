import re


class SectionSplitter:
    """Split ordered pages into ordered, page-aware section fragments."""

    REFERENCE_HEADINGS = {
        "reference",
        "references",
        "bibliography",
        "literature cited",
    }

    def _normalize_heading(self, heading: str) -> str:
        heading = heading.strip()
        heading = re.sub(r"^(?:\*\*|__|[_*])+|(?:\*\*|__|[_*])+$", "", heading)
        return re.sub(r"\s+", " ", heading).strip()

    def _extract_markdown_heading(self, line: str):
        match = re.match(r"^(#{1,6})\s+(.*)", line)
        if match:
            return self._normalize_heading(match.group(2))
        return None

    def _extract_bold_heading(self, line: str):
        match = re.match(r"^\*\*(.+?)\*\*$", line)
        if not match:
            return None

        candidate = self._normalize_heading(match.group(1))
        if len(candidate) <= 160:
            return candidate
        return None

    def _is_reference_heading(self, heading: str) -> bool:
        normalized = re.sub(r"[^a-z ]", "", heading.lower()).strip()
        return normalized in self.REFERENCE_HEADINGS

    def split(self, pages) -> list[dict]:
        """
        Return section fragments in document order.

        Each fragment belongs to a single page so page provenance remains exact.
        The current heading is carried across page boundaries.
        """
        if isinstance(pages, str):
            pages = [{"page_number": 1, "content": pages}]

        fragments = []
        current_section = "UNSPECIFIED"
        skip_reference_content = False

        for page in pages:
            page_number = int(page.get("page_number", 1))
            current_lines = []

            def flush_fragment():
                nonlocal current_lines
                content = "\n".join(current_lines).strip()
                if content and not skip_reference_content:
                    fragments.append({
                        "section": current_section,
                        "page_start": page_number,
                        "page_end": page_number,
                        "content": content,
                    })
                current_lines = []

            for line in page.get("content", "").splitlines():
                stripped = line.strip()
                heading = self._extract_markdown_heading(stripped)
                if not heading:
                    heading = self._extract_bold_heading(stripped)

                if heading:
                    flush_fragment()
                    current_section = heading
                    skip_reference_content = self._is_reference_heading(heading)
                    continue

                current_lines.append(line)

            flush_fragment()

        return fragments
