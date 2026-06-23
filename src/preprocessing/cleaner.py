import re

class MarkdownCleaner:
    def clean(self, markdown: str) -> str:
        """
        Clean extracted markdown text.
        """

        markdown = self._normalize_newlines(markdown)
        markdown = self._remove_hyphenated_linebreaks(markdown)
        markdown = self._remove_extra_spaces(markdown)
        markdown = self._remove_extra_blank_lines(markdown)
        markdown = self._remove_page_artifacts(markdown)

        return markdown.strip()

    def _normalize_newlines(self, text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n")

    def _remove_hyphenated_linebreaks(self, text: str) -> str:
        """
        Convert:
        soy-
        bean
        into:
        soybean
        """
        return re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)

    def _remove_extra_spaces(self, text: str) -> str:
        """
        Replace multiple spaces/tabs with single space.
        """
        return re.sub(r'[ \t]+', ' ', text)

    def _remove_extra_blank_lines(self, text: str) -> str:
        """
        Collapse 3+ blank lines into 2.
        """
        return re.sub(r'\n{3,}', '\n\n', text)

    def _remove_page_artifacts(self, text: str) -> str:
        """
        Remove common page artifacts like page numbers.
        """
        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()

            # Remove isolated page numbers
            if stripped.isdigit():
                continue

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)