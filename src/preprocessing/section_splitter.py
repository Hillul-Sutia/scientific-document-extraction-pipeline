import re

class SectionSplitter:
    def _extract_markdown_heading(self, line: str):
        match = re.match(r'^(#{1,6})\s+(.*)', line)
        if match:
            return match.group(2).strip()
        return None

    def _extract_bold_heading(self, line: str):
        match = re.match(r'^\*\*(.+?)\*\*$', line)
        if match:
            return match.group(1).strip()
        return None

    def split(self, markdown: str) -> dict:
        """
        Split markdown into sections based on headings.
        Returns dictionary:
        {
            section_title: section_content
        }
        """

        sections = {}
        current_section = "UNSPECIFIED"
        current_content = []

        lines = markdown.split("\n")

        for line in lines:
            stripped = line.strip()

            # Detect markdown headings (#, ##, ###)
            heading = self._extract_markdown_heading(stripped)

            # Detect bold headings (**Heading**)
            if not heading:
                heading = self._extract_bold_heading(stripped)

            if heading:
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()

                current_section = heading
                current_content = []
            else:
                current_content.append(line)

        # Save final section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

