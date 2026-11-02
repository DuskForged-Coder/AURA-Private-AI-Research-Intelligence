import logging
import re
import uuid
import zipfile
from pathlib import Path

import fitz
from docx import Document as WordDocument
from docx.opc.exceptions import PackageNotFoundError
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Document, User
from app.retrieval import embed_texts

SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".markdown"}
CHUNK_WORDS = 220
OVERLAP_WORDS = 40
logger = logging.getLogger(__name__)


def extract_text(path: Path, suffix: str) -> list[tuple[int | None, str]]:
    if suffix == ".pdf":
        with fitz.open(path) as pdf:
            return [(index + 1, page.get_text("text")) for index, page in enumerate(pdf)]
    if suffix == ".docx":
        doc = WordDocument(path)
        return [(None, "\n".join(p.text for p in doc.paragraphs))]
    return [(None, path.read_text(encoding="utf-8-sig", errors="replace"))]


def split_chunks(pages: list[tuple[int | None, str]]) -> list[tuple[int | None, str]]:
    output: list[tuple[int | None, str]] = []
    for page, text in pages:
        words = re.findall(r"\S+", text)
        start = 0
        while start < len(words):
            part = " ".join(words[start:start + CHUNK_WORDS]).strip()
            if part:
                output.append((page, part))
            if start + CHUNK_WORDS >= len(words):
                break
            start += CHUNK_WORDS - OVERLAP_WORDS
    return output


async def ingest_upload(upload: UploadFile, owner: User, db: Session) -> Document:
    filename = Path((upload.filename or "").replace("\\", "/")).name
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED:
        raise HTTPException(415, "Supported formats: PDF, DOCX, TXT, and Markdown")

    content = await upload.read(settings.max_upload_bytes + 1)
    if not content:
        raise HTTPException(400, "The uploaded file is empty")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit")

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    document_id = str(uuid.uuid4())
    target = settings.upload_dir / f"{document_id}{suffix}"
    try:
        target.write_bytes(content)
        try:
            if suffix == ".docx":
                with zipfile.ZipFile(target) as archive:
                    entries = archive.infolist()
                    expanded_bytes = sum(entry.file_size for entry in entries)
                    if len(entries) > 10_000 or expanded_bytes > 100 * 1024 * 1024:
                        raise HTTPException(413, "DOCX expands beyond the document processing limit")
            pages = extract_text(target, suffix)
        except (fitz.FileDataError, RuntimeError, zipfile.BadZipFile, PackageNotFoundError) as exc:
            raise HTTPException(422, "Unable to parse this document; verify the file is valid and contains text") from exc
        pieces = split_chunks(pages)
        if not pieces:
            raise HTTPException(422, "No readable text was found in this document")
        document = Document(
            id=document_id,
            owner_id=owner.id,
            filename=filename[:255],
            content_type=upload.content_type or "application/octet-stream",
            size_bytes=len(content),
            storage_path=str(target.resolve()),
            status="ready",
        )
        db.add(document)
        db.flush()
        embeddings = embed_texts([text for _, text in pieces])
        for index, ((page, text), embedding) in enumerate(zip(pieces, embeddings)):
            db.add(Chunk(
                document_id=document.id,
                text=text,
                page_number=page,
                chunk_index=index,
                embedding=embedding,
            ))
        db.commit()
        db.refresh(document)
        return document
    except HTTPException:
        db.rollback()
        target.unlink(missing_ok=True)
        raise
    except Exception:
        db.rollback()
        target.unlink(missing_ok=True)
        logger.exception("Document ingestion failed for document %s", document_id)
        raise
