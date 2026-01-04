from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple

from PyPDF2 import PdfReader

from app.services.ocr.azure_doc_intel import AzureDocIntelOcr


@dataclass
class IngestResult:
    source: str  # "text" | "image" | "pdf"
    text: str

    ocr_used: bool
    ocr_pages: int
    ocr_confidence: Optional[float]


def _pdf_page_count(pdf_bytes: bytes) -> int:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages)


def _extract_pdf_text_per_page(pdf_bytes: bytes) -> List[str]:
    """
    Local text extraction for DIGITAL PDFs (cheap, fast).
    Returns list of text per page (1-indexed conceptually).
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    out: List[str] = []
    for page in reader.pages:
        t = page.extract_text() or ""
        out.append(t.strip())
    return out


def _pages_to_ocr(page_texts: List[str], min_chars: int = 40) -> List[int]:
    """
    Heuristic: if a page has too little embedded text, it’s likely scanned (image-based)
    and needs OCR.
    """
    needs: List[int] = []
    for idx, txt in enumerate(page_texts, start=1):
        if len((txt or "").strip()) < min_chars:
            needs.append(idx)
    return needs


def _compress_pages(pages: List[int]) -> str:
    """
    Convert [1,2,3,5,6,9] -> "1-3,5-6,9" for Document Intelligence `pages` parameter.
    """
    if not pages:
        return ""
    pages = sorted(set(pages))
    ranges: List[Tuple[int, int]] = []

    start = prev = pages[0]
    for p in pages[1:]:
        if p == prev + 1:
            prev = p
        else:
            ranges.append((start, prev))
            start = prev = p
    ranges.append((start, prev))

    parts = []
    for a, b in ranges:
        parts.append(str(a) if a == b else f"{a}-{b}")
    return ",".join(parts)


def ingest(
    *,
    text: Optional[str],
    file_bytes: Optional[bytes],
    filename: Optional[str],
    content_type: Optional[str],
    ocr: AzureDocIntelOcr,
    max_pdf_pages: int,
) -> IngestResult:
    """
    Returns a clean text string for downstream LLM extraction.
    Rules:
    - If `text` exists -> use it, no OCR.
    - If image -> OCR always.
    - If PDF -> try local text extraction first (digital PDFs).
      OCR only pages that look scanned, and only if within page limit.
    """
    # 1) Text
    if text and text.strip():
        return IngestResult(
            source="text",
            text=text.strip(),
            ocr_used=False,
            ocr_pages=0,
            ocr_confidence=None,
        )

    if not file_bytes:
        raise ValueError("Provide either text or a file")

    name = (filename or "").lower()
    ctype = (content_type or "").lower()

    # 2) Image -> OCR
    if ctype.startswith("image/") or name.endswith((".png", ".jpg", ".jpeg")):
        o = ocr.ocr(file_bytes, pages=None)
        merged = "\n\n".join([o.page_text[k] for k in sorted(o.page_text.keys())]).strip()
        return IngestResult(
            source="image",
            text=merged,
            ocr_used=True,
            ocr_pages=len(o.page_text),
            ocr_confidence=o.avg_confidence,
        )

    # 3) PDF -> local extract-first
    if ctype == "application/pdf" or name.endswith(".pdf"):
        total_pages = _pdf_page_count(file_bytes)
        if total_pages > max_pdf_pages:
            raise ValueError(f"PDF has {total_pages} pages; max allowed is {max_pdf_pages}")

        per_page = _extract_pdf_text_per_page(file_bytes)
        needs_ocr = _pages_to_ocr(per_page)

        # Fully digital PDF (all pages had text)
        if not needs_ocr:
            merged = "\n\n".join([t for t in per_page if t]).strip()
            return IngestResult(
                source="pdf",
                text=merged,
                ocr_used=False,
                ocr_pages=0,
                ocr_confidence=None,
            )

        # Mixed/scanned PDF -> OCR only needed pages
        pages_param = _compress_pages(needs_ocr)
        o = ocr.ocr(file_bytes, pages=pages_param)

        merged_pages: List[str] = []
        for i in range(1, len(per_page) + 1):
            local_txt = per_page[i - 1]
            if i in needs_ocr:
                merged_pages.append((o.page_text.get(i) or "").strip())
            else:
                merged_pages.append(local_txt.strip())

        merged = "\n\n".join([t for t in merged_pages if t]).strip()
        return IngestResult(
            source="pdf",
            text=merged,
            ocr_used=True,
            ocr_pages=len(needs_ocr),
            ocr_confidence=o.avg_confidence,
        )

    raise ValueError(f"Unsupported file type: {filename} ({content_type})")
