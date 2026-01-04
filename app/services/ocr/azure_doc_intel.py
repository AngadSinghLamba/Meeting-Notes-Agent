from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Dict, Optional, List

from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential


@dataclass
class OcrResult:
    page_text: Dict[int, str]          # 1-indexed page -> text
    avg_confidence: Optional[float]    # average word confidence when available


class AzureDocIntelOcr:
    def __init__(self, endpoint: str, key: str):
        if not endpoint or not key:
            raise RuntimeError("Missing AZURE_DOC_INTEL_ENDPOINT or AZURE_DOC_INTEL_KEY")

        self._client = DocumentAnalysisClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key),
        )

    def ocr(self, data: bytes, pages: Optional[str] = None) -> OcrResult:
        poller = self._client.begin_analyze_document(
            model_id="prebuilt-read",
            document=io.BytesIO(data),
            pages=pages,
        )
        result = poller.result()

        page_text: Dict[int, str] = {}
        confidences: List[float] = []

        for p in result.pages:
            lines = getattr(p, "lines", None) or []
            page_text[p.page_number] = "\n".join(
                [ln.content for ln in lines if getattr(ln, "content", None)]
            ).strip()

            words = getattr(p, "words", None) or []
            for w in words:
                c = getattr(w, "confidence", None)
                if isinstance(c, (int, float)):
                    confidences.append(float(c))

        avg_conf = (sum(confidences) / len(confidences)) if confidences else None
        return OcrResult(page_text=page_text, avg_confidence=avg_conf)
