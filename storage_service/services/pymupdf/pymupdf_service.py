"""PyMuPDF & PyMuPDF4LLM text & Markdown extraction service.

Uses ``pymupdf4llm`` to convert chapter PDFs into structured Markdown (.md),
extract embedded images into local directories, and output rich Markdown content
preserving chapter headings (#, ##), tables (| ... |), and layout structure.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from storage_service.interfaces.pymupdf_service import IPyMuPDFService
except ImportError:
    from interfaces.pymupdf_service import IPyMuPDFService

logger = logging.getLogger(__name__)


class PyMuPDFService(IPyMuPDFService):
    """PyMuPDF & PyMuPDF4LLM Markdown & Text extraction service."""

    def __init__(self) -> None:
        try:
            import fitz  # noqa: F401
            import pymupdf4llm  # noqa: F401
            self._fitz_available = True
        except ImportError:
            self._fitz_available = False
            logger.warning(
                "PyMuPDF or pymupdf4llm is not installed. "
                "Install with: pip install pymupdf pymupdf4llm"
            )

    def clean_markdown_structure(self, full_md: str) -> str:
        """Post-cleaner pass upgrading Markdown structure to 9.5/10 standard.
        
        1. Strips page footers, series names (Mridang, etc.), and copyright text.
        2. Promotes standalone bold lines to proper Markdown ## headings.
        3. Cleans redundant internal bolding inside headers (# Unit 1 **Name** -> # Unit 1: Name).
        4. Cleans stray pipes in prose text.
        5. Isolates image tags cleanly with double linebreaks.
        """
        if not full_md:
            return ""
        import re

        lines = full_md.splitlines()
        cleaned_lines = []

        for line in lines:
            s = line.strip()

            # 1. Strip page footers and copyright noise
            if re.search(r'reprint\s+\d{4}-\d{2}', s, re.IGNORECASE):
                continue
            if re.match(r'^\d+\s+(?:Mridang|Honeycomb|Beehive|Vasant|Looking Around|Marigold|Shemathi|Sanchayan)\s*$', s, re.IGNORECASE):
                continue
            if re.match(r'^(?:Mridang|Honeycomb|Beehive|Vasant|Looking Around|Marigold|Shemathi|Sanchayan)\s+\d+\s*$', s, re.IGNORECASE):
                continue
            if re.match(r'^\d+\s*$', s):
                continue

            # 2. Promote standalone bold text lines to H2 headings
            m_bold = re.match(r'^\*\*(.+?)\*\*\s*$', s)
            if m_bold:
                content = m_bold.group(1).strip()
                if len(content) < 60 and not content.endswith(('.', ':', '!', '?')):
                    if any(k in content.lower() for k in ["chapter", "unit", "two little", "parts of", "let us", "sight words", "new words", "my family"]):
                        s = f"## {content}"
                    else:
                        s = f"### {content}"

            # 3. Clean headers containing redundant bold asterisks
            if s.startswith("#"):
                s = re.sub(r'\*\*([^*]+)\*\*', r'\1', s)
                s = re.sub(r'\s{2,}', ' ', s)

            # 4. Clean stray pipes in unstructured list/prose text
            if "|" in s and not s.startswith("|"):
                if s.count("|") <= 3 and not re.search(r'^\s*\|.*\|\s*$', s):
                    s = s.replace("|", " • ")

            cleaned_lines.append(s)

        text = "\n".join(cleaned_lines)

        # 5. Isolate image tags cleanly with newlines
        text = re.sub(r'(!\[.*?\]\(.*?\))', r'\n\n\1\n\n', text)

        # 6. Normalize multiple blank lines to double newlines
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    async def extract_markdown(
        self,
        pdf_path: Path,
        images_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Converts a PDF to structured Markdown using pymupdf4llm.
        
        Saves embedded images to images_dir if specified.
        Returns:
        * full_markdown (str): The complete chapter Markdown text
        * page_chunks (list[dict]): Per-page markdown chunks with metadata
        * total_pages (int): Page count
        """
        def _do_extract_md() -> Dict[str, Any]:
            import pymupdf4llm
            import fitz

            doc = fitz.open(str(pdf_path))
            total_pages = doc.page_count
            doc.close()

            img_path_str = str(images_dir) if images_dir else None
            if images_dir:
                images_dir.mkdir(parents=True, exist_ok=True)

            logger.info(
                "PyMuPDF4LLM Markdown conversion started: %s (%d pages, img_dir=%s)",
                pdf_path.name, total_pages, img_path_str
            )

            # Convert PDF to structured Markdown with images written to images_dir
            full_md_raw = pymupdf4llm.to_markdown(
                str(pdf_path),
                write_images=bool(images_dir),
                image_path=img_path_str,
            )

            # Apply Automated Markdown Post-Cleaner pass (Footers, Headings, Images, Pipes)
            full_md = self.clean_markdown_structure(full_md_raw)

            # Also get page chunks for page-level alignment
            page_chunks_raw = pymupdf4llm.to_markdown(
                str(pdf_path),
                page_chunks=True,
            )

            pages = []
            for p_idx, chunk in enumerate(page_chunks_raw):
                text = chunk.get("text", "")
                words = len(text.split()) if text.strip() else 0
                pages.append({
                    "page_number": p_idx + 1,
                    "plain_text": text,
                    "word_count": words,
                    "token_count": int(words * 1.3),
                    "metadata": chunk.get("metadata", {}),
                })

            logger.info("PyMuPDF4LLM Markdown conversion complete: %d pages", total_pages)

            return {
                "full_markdown": full_md,
                "pages": pages,
                "total_pages": total_pages,
            }

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _do_extract_md)

    async def extract_pages(
        self,
        pdf_path: Path,
        book_id: str = "",
    ) -> Dict[str, Any]:
        """Extract text from every page of a PDF."""
        res = await self.extract_markdown(pdf_path)
        return {
            "pages": res["pages"],
            "total_pages": res["total_pages"],
            "full_markdown": res["full_markdown"],
        }

    async def extract_toc(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Extract Table of Contents (TOC) or chapter headings from PDF.
        
        Returns a list of TOC entries:
        [
            {"level": 1, "title": "Chapter 1: Motion", "page": 1},
            ...
        ]
        """
        def _do_extract_toc() -> List[Dict[str, Any]]:
            import fitz
            import re
            
            toc_entries = []
            try:
                doc = fitz.open(str(pdf_path))
                raw_toc = doc.get_toc() # List of [level, title, page]
                if raw_toc:
                    for item in raw_toc:
                        if len(item) >= 3:
                            lvl, title, page = item[0], item[1].strip(), item[2]
                            if title:
                                toc_entries.append({
                                    "level": lvl,
                                    "title": title,
                                    "page": page
                                })
                
                # Fallback: if doc.get_toc() is empty, scan first 10 pages for Chapter titles or headings
                if not toc_entries:
                    ch_pattern = re.compile(r'^(?:Chapter\s+\d+|CHAPTER\s+\d+|Unit\s+\d+|\d+\.\s+[A-Z]).*', re.MULTILINE)
                    limit = min(10, doc.page_count)
                    for p_idx in range(limit):
                        page_text = doc[p_idx].get_text()
                        matches = ch_pattern.findall(page_text)
                        for match in matches:
                            clean_t = match.strip()
                            if clean_t and clean_t not in [e["title"] for e in toc_entries]:
                                toc_entries.append({
                                    "level": 1,
                                    "title": clean_t,
                                    "page": p_idx + 1
                                })
                doc.close()
            except Exception as e:
                logger.warning(f"Failed to extract TOC from {pdf_path}: {e}")

            return toc_entries

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _do_extract_toc)

