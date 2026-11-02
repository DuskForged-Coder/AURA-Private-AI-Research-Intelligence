from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import Base, engine, get_db
from app.ingestion import ingest_upload
from app.models import Conversation, Document, Message, User
from app.retrieval import generate_answer, search_documents
from app.schemas import (
    AskIn,
    AskOut,
    Citation,
    ConversationDetail,
    ConversationOut,
    DocumentOut,
    QueryIn,
    SearchOut,
    TokenOut,
    UserCreate,
    UserOut,
)
from app.security import create_access_token, get_current_user, hash_password, verify_password

def initialize_database() -> None:
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="AURA API",
    version="0.1.0",
    description="Local-first document research",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
@app.get("/api/v1/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.post("/api/v1/auth/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with that email already exists")
    return user


@app.post("/api/v1/auth/login", response_model=TokenOut)
def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.email == username.strip().lower()))
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    return TokenOut(access_token=create_access_token(user.id))


@app.get("/api/v1/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@app.post("/api/v1/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await ingest_upload(file, user, db)


@app.get("/api/v1/documents", response_model=list[DocumentOut])
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Document).where(Document.owner_id == user.id).order_by(Document.created_at.desc())
    ).all()


@app.get("/api/v1/documents/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.owner_id == user.id)
    )
    if document is None:
        raise HTTPException(404, "Document not found")
    return document


@app.delete("/api/v1/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.owner_id == user.id)
    )
    if document is None:
        raise HTTPException(404, "Document not found")
    storage_path = Path(document.storage_path)
    db.delete(document)
    db.commit()
    storage_path.unlink(missing_ok=True)


@app.post("/api/v1/search", response_model=SearchOut)
def search(
    payload: QueryIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return SearchOut(query=payload.query, results=search_documents(db, user, payload.query, payload.limit))


@app.post("/api/v1/ask", response_model=AskOut)
def ask(
    payload: AskIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.conversation_id:
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.id == payload.conversation_id,
                Conversation.owner_id == user.id,
            )
        )
        if conversation is None:
            raise HTTPException(404, "Conversation not found")
    else:
        conversation = Conversation(owner_id=user.id, title=payload.query[:80])
        db.add(conversation)
        db.flush()

    citations = search_documents(db, user, payload.query, payload.limit)
    answer, abstained = generate_answer(payload.query, citations)
    db.add(Message(conversation_id=conversation.id, role="user", content=payload.query))
    db.add(Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        citations=citations,
    ))
    db.commit()
    return AskOut(
        conversation_id=conversation.id,
        answer=answer,
        abstained=abstained,
        citations=[Citation(**item) for item in citations],
    )


@app.get("/api/v1/conversations", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Conversation)
        .where(Conversation.owner_id == user.id)
        .order_by(Conversation.created_at.desc())
    ).all()


@app.get("/api/v1/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id, Conversation.owner_id == user.id)
    )
    if conversation is None:
        raise HTTPException(404, "Conversation not found")
    return conversation
