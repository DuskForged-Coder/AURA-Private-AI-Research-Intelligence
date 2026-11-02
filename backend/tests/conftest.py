import os
from pathlib import Path
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["UPLOAD_DIR"] = str(Path(tempfile.gettempdir()) / "aura-test-uploads")
os.environ["JWT_SECRET_KEY"] = "test-only-signing-key-never-use-in-production"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def register_and_login(client: TestClient, email: str):
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "research-password-123"},
    )
    assert registration.status_code == 201, registration.text
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "research-password-123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth_headers(client):
    return register_and_login(client, "reader@example.com")
