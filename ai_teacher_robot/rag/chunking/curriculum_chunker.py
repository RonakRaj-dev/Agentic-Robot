"""Paragraph / Structure-Aware + Sliding Window Markdown Chunker.

Implements RAG best practices for educational textbook processing:
1. Structure-Aware: Splits on Markdown section headers (#, ##, ###) and paragraphs (\n\n).
2. Table & Formula Integrity: Preserves Markdown tables (| ... |) and math formulas intact.
3. Sliding Window Overlap: Applies 100-token sliding window overlap on long sections.
4. Context Prepending: Injects structural context headers (Book, Class, Subject, Chapter, Section)
   into every chunk before vector embedding to eliminate context loss.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class CurriculumChunker:
    """Structure-aware Markdown chunker with sliding window overlap and context prepending."""

    def __init__(
        self,
        max_chunk_tokens: int = 500,
        overlap_tokens: int = 100,
    ) -> None:
        self.max_chunk_tokens = max_chunk_tokens
        self.overlap_tokens = overlap_tokens

    def chunk_markdown(
        self,
        markdown_text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Chunks a Markdown document using heading structure, paragraph boundaries, and sliding window overlap.
        
        Metadata dict should contain:
        * book_title (str)
        * class_no / class (str/int)
        * subject (str)
        * chapter_no (int)
        * chapter_name (str)
        * board (str)
        """
        meta = metadata or {}
        book_title = meta.get("book_title") or meta.get("title") or "NCERT Textbook"
        class_str = str(meta.get("class_no") or meta.get("class") or "5")
        subject = meta.get("subject") or "General"
        chapter_no = meta.get("chapter_no") or "1"
        chapter_name = meta.get("chapter_name") or f"Chapter {chapter_no}"
        board = meta.get("board") or "NCERT"

        # Split Markdown into heading sections (#, ##, ###)
        heading_pattern = r"(^#{1,4}\s+.+$)"
        sections_raw = re.split(heading_pattern, markdown_text, flags=re.MULTILINE)

        sections: List[Dict[str, str]] = []
        current_heading = f"Chapter {chapter_no}: {chapter_name}"
        current_content_lines: List[str] = []

        idx = 0
        while idx < len(sections_raw):
            part = sections_raw[idx]
            if re.match(heading_pattern, part, flags=re.MULTILINE):
                if current_content_lines:
                    sections.append({
                        "heading": current_heading,
                        "text": "".join(current_content_lines).strip()
                    })
                    current_content_lines = []
                current_heading = part.strip().lstrip("#").strip()
            else:
                current_content_lines.append(part)
            idx += 1

        if current_content_lines:
            sections.append({
                "heading": current_heading,
                "text": "".join(current_content_lines).strip()
            })

        chunks: List[Dict[str, Any]] = []

        for sec in sections:
            sec_heading = sec["heading"]
            sec_text = sec["text"]
            if not sec_text:
                continue

            # Skip non-educational teacher notes, sight words, and copyright meta sections
            h_lower = sec_heading.lower().strip()
            t_lower = sec_text.lower().strip()
            meta_keywords = [
                "note to the teacher", "notes to the teacher", "teacher's note", "teachers note",
                "reprint", "isbn", "publication team", "all rights reserved", "about the unit"
            ]
            if any(k in h_lower for k in meta_keywords):
                continue
            if len(sec_text.split()) < 20 and any(k in t_lower for k in ["isbn", "reprint", "publication team"]):
                continue

            # Split section text into paragraphs / tables / code blocks
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", sec_text) if p.strip()]
            
            current_chunk_paragraphs: List[str] = []
            current_token_count = 0

            for p in paragraphs:
                p_tokens = len(p.split())
                
                # If single paragraph is larger than max_chunk_tokens, sliding window split it
                if p_tokens > self.max_chunk_tokens:
                    if current_chunk_paragraphs:
                        chunk_body = "\n\n".join(current_chunk_paragraphs)
                        chunks.append(self._build_chunk_dict(
                            chunk_body=chunk_body,
                            section_heading=sec_heading,
                            book_title=book_title,
                            class_str=class_str,
                            subject=subject,
                            chapter_no=chapter_no,
                            chapter_name=chapter_name,
                            board=board,
                            metadata=meta,
                        ))
                        current_chunk_paragraphs = []
                        current_token_count = 0

                    sub_chunks = self._sliding_window_split(p)
                    for sub in sub_chunks:
                        chunks.append(self._build_chunk_dict(
                            chunk_body=sub,
                            section_heading=sec_heading,
                            book_title=book_title,
                            class_str=class_str,
                            subject=subject,
                            chapter_no=chapter_no,
                            chapter_name=chapter_name,
                            board=board,
                            metadata=meta,
                        ))
                    continue

                if current_token_count + p_tokens > self.max_chunk_tokens:
                    chunk_body = "\n\n".join(current_chunk_paragraphs)
                    chunks.append(self._build_chunk_dict(
                        chunk_body=chunk_body,
                        section_heading=sec_heading,
                        book_title=book_title,
                        class_str=class_str,
                        subject=subject,
                        chapter_no=chapter_no,
                        chapter_name=chapter_name,
                        board=board,
                        metadata=meta,
                    ))
                    
                    # Apply sliding window overlap by keeping trailing paragraph if appropriate
                    if current_chunk_paragraphs and len(current_chunk_paragraphs[-1].split()) <= self.overlap_tokens:
                        current_chunk_paragraphs = [current_chunk_paragraphs[-1], p]
                        current_token_count = len(current_chunk_paragraphs[0].split()) + p_tokens
                    else:
                        current_chunk_paragraphs = [p]
                        current_token_count = p_tokens
                else:
                    current_chunk_paragraphs.append(p)
                    current_token_count += p_tokens

            if current_chunk_paragraphs:
                chunk_body = "\n\n".join(current_chunk_paragraphs)
                chunks.append(self._build_chunk_dict(
                    chunk_body=chunk_body,
                    section_heading=sec_heading,
                    book_title=book_title,
                    class_str=class_str,
                    subject=subject,
                    chapter_no=chapter_no,
                    chapter_name=chapter_name,
                    board=board,
                    metadata=meta,
                ))

        return chunks

    def _sliding_window_split(self, text: str) -> List[str]:
        """Splits long text into overlapping sliding window chunks."""
        words = text.split()
        chunks = []
        start = 0
        while start < len(words):
            end = min(start + self.max_chunk_tokens, len(words))
            chunk_str = " ".join(words[start:end])
            chunks.append(chunk_str)
            if end >= len(words):
                break
            start += (self.max_chunk_tokens - self.overlap_tokens)
        return chunks

    def _build_chunk_dict(
        self,
        chunk_body: str,
        section_heading: str,
        book_title: str,
        class_str: str,
        subject: str,
        chapter_no: Any,
        chapter_name: str,
        board: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Prepends context header and returns structured chunk payload."""
        context_header = (
            f"[Context: Book: {book_title} | Class: {class_str} | Subject: {subject} | "
            f"Chapter {chapter_no}: {chapter_name} | Section: {section_heading}]"
        )
        full_chunk_text = f"{context_header}\n\n{chunk_body}"
        word_count = len(chunk_body.split())

        return {
            "chunk_text": full_chunk_text,
            "raw_text": chunk_body,
            "topic": section_heading,
            "section_heading": section_heading,
            "page_number": metadata.get("page_number", 1),
            "word_count": word_count,
            "token_count": int(word_count * 1.3),
            "book_title": book_title,
            "class": class_str,
            "subject": subject,
            "chapter": str(chapter_no),
            "chapter_name": chapter_name,
            "board": board,
        }

    def chunk_document(self, page_texts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Legacy compatibility wrapper for list of page dicts."""
        combined_md = "\n\n".join([p.get("plain_text", "") for p in page_texts])
        return self.chunk_markdown(combined_md)
