from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from pypdf import PdfReader

from langchain_text_splitters import RecursiveCharacterTextSplitter

from .models import Document, DocumentChunk
from monitoring.services import task_create, task_fail, task_info, task_succeed


@dataclass(frozen=True)
class ParseResult:
    text: str
    pages: int
    chunks: int


def _try_ocr_pdf(pdf_path: Path) -> str:
    try:
        import fitz
        import numpy as np
        import cv2
        from rapidocr_onnxruntime import RapidOCR
    except Exception:
        return ""

    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return ""

    ocr = RapidOCR()
    pages_text: list[str] = []
    total_len = 0
    try:
        max_pages = min(len(doc), int(getattr(settings, "PDF_OCR_MAX_PAGES", 30)))
        scale = float(getattr(settings, "PDF_OCR_SCALE", 1.6))
        for i in range(max_pages):
            page = doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            elif pix.n == 3:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            else:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            res, _elapse = ocr(img)
            if not res:
                pages_text.append("")
                continue
            lines = []
            for item in res:
                if not item or len(item) < 2:
                    continue
                text = item[1]
                if isinstance(text, str) and text.strip():
                    lines.append(text.strip())
            page_text = "\n".join(lines).strip()
            pages_text.append(page_text)
            total_len += len(page_text)
            if total_len >= int(getattr(settings, "PDF_OCR_EARLY_STOP_LEN", 2500)):
                break
    finally:
        doc.close()

    return "\n".join([t for t in pages_text if t]).strip()


def parse_pdf_to_text(document: Document) -> ParseResult:
    t = task_create(task_type="parse", document_id=str(document.id))
    try:
        pdf_path = Path(settings.MEDIA_ROOT) / document.file.name
        reader = PdfReader(str(pdf_path))
        pages_text: list[str] = []
        for page in reader.pages:
            pages_text.append(page.extract_text() or "")
        full_text = "\n".join([t for t in pages_text if t]).strip()
        used_ocr = False
        if len(full_text) < 30:
            ocr_text = _try_ocr_pdf(pdf_path)
            if ocr_text:
                full_text = ocr_text
                used_ocr = True

        document.parsed_text = full_text
        if not full_text:
            document.status = Document.Status.FAILED
            document.error_message = (
                "未能从 PDF 提取到可用文本。该文件可能为扫描件（图片型 PDF）。"
                "已尝试 OCR 但仍失败，请检查 PDF 清晰度或更换版本。"
            )
        else:
            document.status = Document.Status.PARSED
            document.error_message = ""
        document.save(update_fields=["parsed_text", "status", "error_message"])

        DocumentChunk.objects.filter(document=document).delete()
        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120, separators=["\n\n", "\n", "。", "；", "，", " "])
        chunks = splitter.split_text(full_text) if full_text else []
        bulk = []
        for idx, content in enumerate(chunks):
            bulk.append(DocumentChunk(document=document, chunk_index=idx, content=content))
        if bulk:
            DocumentChunk.objects.bulk_create(bulk)

        msg = f"parsed_pages={len(reader.pages)} chunks={len(chunks)} ocr={'1' if used_ocr else '0'}"
        task_info(t, message=msg)
        if not full_text:
            task_fail(t, error=document.error_message)
        else:
            task_succeed(t)
        return ParseResult(text=full_text, pages=len(reader.pages), chunks=len(chunks))
    except Exception as e:
        document.status = Document.Status.FAILED
        document.error_message = str(e)
        document.save(update_fields=["status", "error_message"])
        task_fail(t, error=str(e))
        raise

