from docx import Document as WordDocument

from conftest import register_and_login
from app.ingestion import extract_text


def test_auth_document_upload_search_and_citations(client, auth_headers):
    assert client.get("/api/v1/documents", headers=auth_headers).status_code == 200
    content = (
        b"AURA preserves research sources locally. "
        b"Every generated answer must be supported by inspectable citations."
    )
    uploaded = client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("research.txt", content, "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    assert document["status"] == "ready"

    results = client.post(
        "/api/v1/search",
        headers=auth_headers,
        json={"query": "inspectable citations"},
    )
    assert results.status_code == 200
    assert results.json()["results"][0]["filename"] == "research.txt"

    answer = client.post(
        "/api/v1/ask",
        headers=auth_headers,
        json={"query": "What supports generated answers?"},
    )
    assert answer.status_code == 200
    assert answer.json()["abstained"] is False
    assert answer.json()["citations"][0]["source_id"] == document["id"]
    conversation_id = answer.json()["conversation_id"]
    assert client.get(f"/api/v1/conversations/{conversation_id}", headers=auth_headers).status_code == 200

    deleted = client.delete(f"/api/v1/documents/{document['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get("/api/v1/documents", headers=auth_headers).json() == []


def test_users_cannot_access_anothers_documents_or_conversations(client, auth_headers):
    doc = client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("private.md", b"Private notes about confidential project A.", "text/markdown")},
    ).json()
    conversation = client.post(
        "/api/v1/ask",
        headers=auth_headers,
        json={"query": "confidential project"},
    ).json()
    other = register_and_login(client, "other@example.com")

    assert client.get(f"/api/v1/documents/{doc['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/v1/documents/{doc['id']}", headers=other).status_code == 404
    assert client.post(
        "/api/v1/search", headers=other, json={"query": "confidential"}
    ).json()["results"] == []
    assert client.get(
        f"/api/v1/conversations/{conversation['conversation_id']}", headers=other
    ).status_code == 404
    assert client.post(
        "/api/v1/ask",
        headers=other,
        json={"query": "private", "conversation_id": conversation["conversation_id"]},
    ).status_code == 404


def test_upload_validation_and_authentication(client, auth_headers):
    assert client.get("/api/v1/documents").status_code == 401
    unsupported = client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("payload.exe", b"not a document", "application/octet-stream")},
    )
    assert unsupported.status_code == 415
    empty = client.post(
        "/api/v1/documents",
        headers=auth_headers,
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert empty.status_code == 400


def test_rejects_malformed_pdf_and_docx(client, auth_headers):
    for filename, content in (
        ("broken.pdf", b"not a PDF"),
        ("broken.docx", b"not a DOCX archive"),
    ):
        response = client.post(
            "/api/v1/documents",
            headers=auth_headers,
            files={"file": (filename, content, "application/octet-stream")},
        )
        assert response.status_code == 422
    assert client.get("/api/v1/documents", headers=auth_headers).json() == []


def test_abstains_without_relevant_evidence(client, auth_headers):
    result = client.post(
        "/api/v1/ask",
        headers=auth_headers,
        json={"query": "What is the orbital period of Mars?"},
    )
    assert result.status_code == 200
    assert result.json()["abstained"] is True
    assert result.json()["citations"] == []


def test_extracts_supported_text_formats(tmp_path):
    txt = tmp_path / "note.txt"
    txt.write_text("plain text evidence", encoding="utf-8")
    md = tmp_path / "note.md"
    md.write_text("# Markdown evidence", encoding="utf-8")
    docx_path = tmp_path / "note.docx"
    word = WordDocument()
    word.add_paragraph("DOCX evidence")
    word.save(docx_path)

    assert "plain text evidence" in extract_text(txt, ".txt")[0][1]
    assert "Markdown evidence" in extract_text(md, ".md")[0][1]
    assert "DOCX evidence" in extract_text(docx_path, ".docx")[0][1]

    import fitz
    pdf_path = tmp_path / "note.pdf"
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "PDF page evidence")
    pdf.save(pdf_path)
    pdf.close()
    extracted = extract_text(pdf_path, ".pdf")
    assert extracted[0][0] == 1
    assert "PDF page evidence" in extracted[0][1]
