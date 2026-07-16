import hashlib
import re

from src.utils.token_count import get_tokenizer


class Chunker:
    """Build ordered, token-bounded chunks while preserving source metadata."""

    def __init__(
        self,
        target_tokens: int = 550,
        min_tokens: int = 200,
        max_tokens: int = 750,
        overlap_tokens: int = 80,
        tokenizer=None,
    ):
        if not 0 <= overlap_tokens < max_tokens:
            raise ValueError("overlap_tokens must be smaller than max_tokens")
        if not min_tokens <= target_tokens <= max_tokens:
            raise ValueError("Expected min_tokens <= target_tokens <= max_tokens")

        self.target_tokens = target_tokens
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self._tokenizer = tokenizer

    @property
    def tokenizer(self):
        if self._tokenizer is None:
            self._tokenizer = get_tokenizer()
        return self._tokenizer

    def _encode(self, text: str):
        return self.tokenizer.encode(text, add_special_tokens=False)

    def _decode(self, token_ids) -> str:
        return self.tokenizer.decode(token_ids, skip_special_tokens=True).strip()

    def _count(self, text: str) -> int:
        return len(self._encode(text))

    def _split_sentences(self, text: str) -> list[str]:
        normalized = re.sub(r"[ \t]+", " ", text).strip()
        if not normalized:
            return []

        sentences = re.split(
            r"(?<=[.!?])\s+(?=[A-Z0-9\[\(])|\n+",
            normalized,
        )
        return [sentence.strip() for sentence in sentences if sentence.strip()]

    def _split_oversized_unit(self, text: str) -> list[str]:
        token_ids = self._encode(text)
        if len(token_ids) <= self.max_tokens:
            return [text]

        step = self.max_tokens - self.overlap_tokens
        parts = []
        for start in range(0, len(token_ids), step):
            part = self._decode(token_ids[start:start + self.max_tokens])
            if part:
                parts.append(part)
            if start + self.max_tokens >= len(token_ids):
                break
        return parts

    def _tail_for_overlap(self, units: list[dict]) -> list[dict]:
        if self.overlap_tokens == 0:
            return []

        selected = []
        for unit in reversed(units):
            candidate = [unit] + selected
            text = " ".join(item["text"] for item in candidate)
            if self._count(text) > self.overlap_tokens and selected:
                break
            selected = candidate
            if self._count(text) >= self.overlap_tokens:
                break
        return selected

    def _make_raw_chunk(
        self,
        chunk_type: str,
        section: str,
        content: str,
        page_start: int,
        page_end: int,
        caption=None,
    ) -> dict:
        return {
            "chunk_type": chunk_type,
            "section": section,
            "content": content.strip(),
            "caption": caption,
            "page_start": int(page_start),
            "page_end": int(page_end),
        }

    def _text_chunks(self, blocks: list[dict]) -> list[dict]:
        chunks = []
        buffer = []
        buffer_has_new_content = False
        current_section = None

        def flush():
            nonlocal buffer, buffer_has_new_content
            if not buffer:
                return
            if not buffer_has_new_content:
                buffer = []
                return
            chunks.append(self._make_raw_chunk(
                chunk_type="text",
                section=current_section or "UNSPECIFIED",
                content=" ".join(unit["text"] for unit in buffer),
                page_start=min(unit["page_start"] for unit in buffer),
                page_end=max(unit["page_end"] for unit in buffer),
            ))
            buffer = []
            buffer_has_new_content = False

        for block in blocks:
            section = block.get("section", "UNSPECIFIED")
            if current_section is not None and section != current_section:
                flush()
            current_section = section

            for sentence in self._split_sentences(block.get("content", "")):
                for part in self._split_oversized_unit(sentence):
                    unit = {
                        "text": part,
                        "page_start": block.get("page_start", 1),
                        "page_end": block.get("page_end", 1),
                    }
                    candidate = buffer + [unit]
                    candidate_text = " ".join(item["text"] for item in candidate)

                    if buffer and self._count(candidate_text) > self.max_tokens:
                        previous = list(buffer)
                        flush()
                        buffer = self._tail_for_overlap(previous)
                        buffer_has_new_content = False

                        overlap_candidate = buffer + [unit]
                        overlap_text = " ".join(
                            item["text"] for item in overlap_candidate
                        )
                        if buffer and self._count(overlap_text) > self.max_tokens:
                            buffer = []

                    buffer.append(unit)
                    buffer_has_new_content = True

                    buffer_text = " ".join(item["text"] for item in buffer)
                    if self._count(buffer_text) >= self.target_tokens:
                        previous = list(buffer)
                        flush()
                        buffer = self._tail_for_overlap(previous)
                        buffer_has_new_content = False

        flush()
        return chunks

    def _table_chunks(self, block: dict) -> list[dict]:
        content = block.get("content", "").strip()
        caption = block.get("caption")
        full_text = f"{caption or ''}\n{content}".strip()

        if self._count(full_text) <= self.max_tokens:
            return [self._make_raw_chunk(
                "table",
                block.get("section", "UNSPECIFIED"),
                content,
                block.get("page_start", 1),
                block.get("page_end", 1),
                caption,
            )]

        lines = [line for line in content.splitlines() if line.strip()]
        header = lines[:2] if len(lines) >= 2 else lines[:1]
        rows = lines[len(header):]
        grouped_rows = []
        current_rows = []

        for row in rows:
            candidate_rows = current_rows + [row]
            candidate = "\n".join(header + candidate_rows)
            candidate_text = f"{caption or ''}\n{candidate}".strip()
            if current_rows and self._count(candidate_text) > self.max_tokens:
                grouped_rows.append(current_rows)
                current_rows = [row]
            else:
                current_rows = candidate_rows

        if current_rows or not rows:
            grouped_rows.append(current_rows)

        return [
            self._make_raw_chunk(
                "table",
                block.get("section", "UNSPECIFIED"),
                "\n".join(header + row_group),
                block.get("page_start", 1),
                block.get("page_end", 1),
                caption,
            )
            for row_group in grouped_rows
        ]

    def _finalize_chunks(
        self,
        chunks: list[dict],
        document_id: str,
        source_pdf: str,
    ) -> list[dict]:
        safe_document_id = re.sub(r"[^A-Za-z0-9_-]+", "_", document_id).strip("_")
        safe_document_id = safe_document_id[:80] or "document"

        for index, chunk in enumerate(chunks, start=1):
            identity = "|".join([
                document_id,
                str(chunk["page_start"]),
                str(chunk["page_end"]),
                chunk["section"],
                chunk["chunk_type"],
                chunk["content"],
            ])
            content_hash = hashlib.sha256(identity.encode("utf-8")).hexdigest()
            chunk_id = f"{safe_document_id}_c{index:05d}_{content_hash[:8]}"

            embedding_parts = [
                f"Document: {source_pdf}",
                f"Section: {chunk['section']}",
                f"Type: {chunk['chunk_type']}",
            ]
            if chunk.get("caption"):
                embedding_parts.append(f"Caption: {chunk['caption']}")
            embedding_parts.append(f"Content:\n{chunk['content']}")

            chunk.update({
                "chunk_id": chunk_id,
                "document_id": document_id,
                "source_pdf": source_pdf,
                "chunk_index": index,
                "token_count": self._count(chunk["content"]),
                "content_hash": content_hash,
                "embedding_text": "\n".join(embedding_parts),
            })

        for index, chunk in enumerate(chunks):
            chunk["previous_chunk_id"] = (
                chunks[index - 1]["chunk_id"] if index > 0 else None
            )
            chunk["next_chunk_id"] = (
                chunks[index + 1]["chunk_id"]
                if index + 1 < len(chunks)
                else None
            )

        return chunks

    def chunk(
        self,
        parsed_blocks,
        document_id: str = "document",
        source_pdf: str = "document.pdf",
    ) -> list[dict]:
        """Convert ordered blocks into enriched text and table chunks."""
        if isinstance(parsed_blocks, dict):
            legacy_blocks = []
            for section, section_data in parsed_blocks.items():
                for content in section_data.get("text_blocks", []):
                    legacy_blocks.append({
                        "block_type": "text",
                        "section": section,
                        "page_start": 1,
                        "page_end": 1,
                        "content": content,
                        "caption": None,
                    })
                for content in section_data.get("tables", []):
                    legacy_blocks.append({
                        "block_type": "table",
                        "section": section,
                        "page_start": 1,
                        "page_end": 1,
                        "content": content,
                        "caption": None,
                    })
            parsed_blocks = legacy_blocks

        raw_chunks = []
        pending_text_blocks = []

        def flush_text_blocks():
            nonlocal pending_text_blocks
            if pending_text_blocks:
                raw_chunks.extend(self._text_chunks(pending_text_blocks))
                pending_text_blocks = []

        for block in parsed_blocks:
            if block.get("block_type") == "table":
                flush_text_blocks()
                raw_chunks.extend(self._table_chunks(block))
            elif block.get("content", "").strip():
                pending_text_blocks.append(block)

        flush_text_blocks()
        return self._finalize_chunks(raw_chunks, document_id, source_pdf)
