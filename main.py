"""Student Result Management Portal - secure backend.

Auth: bcrypt password hashing + JWT bearer tokens.
Authorization: role checks (student / teacher / admin) on every endpoint.
"""
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import bcrypt
import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import (Boolean, Column, DateTime, Float, Integer, String,
                        UniqueConstraint, create_engine)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from ai_recommend import detect_weak_topics, generate_recommendation

load_dotenv()
log = logging.getLogger("portal")

# ---------------------------------------------------------------- config
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/student_portal_db"
)
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    JWT_SECRET = secrets.token_urlsafe(48)
    log.warning("JWT_SECRET not set - using a random one (tokens reset on restart).")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.environ.get("TOKEN_EXPIRE_MINUTES", "60"))
ALLOWED_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
SEED_DEMO = os.environ.get("SEED_DEMO", "1") == "1"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@12345")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)  # bcrypt hash
    role = Column(String(20), nullable=False)  # student | teacher | admin
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    department = Column(String(20), nullable=True, index=True)  # CSE, IT, ECE, ...
    year = Column(Integer, nullable=True, index=True)  # 1-4 (current year of study)
    created_at = Column(DateTime(timezone=True), default=now)


class Result(Base):
    __tablename__ = "results"
    __table_args__ = (UniqueConstraint("student_roll", "subject", name="uq_result"),)
    id = Column(Integer, primary_key=True, index=True)
    student_roll = Column(String(50), index=True, nullable=False)
    student_name = Column(String(100), nullable=False)
    subject = Column(String(100), nullable=False)
    marks = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)


class TopicResult(Base):
    __tablename__ = "topic_results"
    __table_args__ = (UniqueConstraint("student_roll", "subject", "topic", name="uq_topic"),)
    id = Column(Integer, primary_key=True, index=True)
    student_roll = Column(String(50), index=True, nullable=False)
    subject = Column(String(100), nullable=False)
    topic = Column(String(100), nullable=False)
    marks = Column(Float, nullable=False)
    max_marks = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now)


class LoginLog(Base):
    __tablename__ = "login_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50))
    role = Column(String(20))
    success = Column(Boolean, default=True)
    login_time = Column(DateTime(timezone=True), default=now)


# ---------------------------------------------------------------- schemas
class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterRequest(BaseModel):
    user_id: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def strong(cls, v: str) -> str:
        if not (any(c.isalpha() for c in v) and any(c.isdigit() for c in v)):
            raise ValueError("Password must contain letters and numbers")
        return v


class AdminCreateUser(RegisterRequest):
    role: str = Field(pattern="^(student|teacher|admin)$")


class LoginRequest(BaseModel):
    user_id: str
    password: str
    role: str = Field(pattern="^(student|teacher|admin)$")


class UserOut(ORM):
    id: int
    user_id: str
    name: str
    role: str
    is_active: bool
    department: Optional[str] = None
    year: Optional[int] = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ResultIn(BaseModel):
    student_roll: str = Field(min_length=1, max_length=50)
    subject: str = Field(min_length=1, max_length=100)
    marks: float = Field(ge=0, le=100)


class ResultOut(ORM):
    id: int
    student_roll: str
    student_name: str
    subject: str
    marks: float
    grade: str = ""
    created_at: datetime
    updated_at: Optional[datetime] = None


class TopicIn(BaseModel):
    student_roll: str = Field(min_length=1, max_length=50)
    subject: str = Field(min_length=1, max_length=100)
    topic: str = Field(min_length=1, max_length=100)
    marks: float = Field(ge=0)
    max_marks: float = Field(gt=0)


class TopicOut(ORM):
    id: int
    student_roll: str
    subject: str
    topic: str
    marks: float
    max_marks: float
    created_at: datetime


class LogOut(ORM):
    user_id: Optional[str]
    role: Optional[str]
    success: bool
    login_time: datetime


# ---------------------------------------------------------------- security
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


_DUMMY_HASH = hash_password("dummy-password-for-timing")
bearer = HTTPBearer(auto_error=False)


def create_token(user: User) -> str:
    payload = {
        "sub": user.user_id,
        "role": user.role,
        "exp": now() + timedelta(minutes=TOKEN_EXPIRE_MINUTES),
        "iat": now(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers={"WWW-Authenticate": "Bearer"}
    )
    if not creds:
        raise unauthorized
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Please log in again.")
    except jwt.PyJWTError:
        raise unauthorized
    user = db.query(User).filter(User.user_id == payload.get("sub")).first()
    if not user or not user.is_active:
        raise unauthorized
    return user


def require_roles(*roles: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission for this action")
        return user

    return checker


def can_access_student(user: User, roll: str) -> None:
    if user.role == "student" and user.user_id != roll:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Students can only access their own data")


def grade_for(marks: float) -> str:
    for cutoff, g in ((90, "A+"), (80, "A"), (70, "B+"), (60, "B"), (50, "C")):
        if marks >= cutoff:
            return g
    return "F"


def result_out(r: Result) -> ResultOut:
    out = ResultOut.model_validate(r)
    out.grade = grade_for(r.marks)
    return out


# ---------------------------------------------------------------- app
def seed(db: Session) -> None:
    if db.query(User).count() > 0:
        return
    users = [User(user_id="A001", password=hash_password(ADMIN_PASSWORD), role="admin", name="Admin User")]
    if SEED_DEMO:
        users += [
            User(user_id="T001", password=hash_password("Teach@123"), role="teacher", name="Prof. Johnson"),
            User(user_id="S001", password=hash_password("Pass@1234"), role="student", name="John Doe"),
            User(user_id="S002", password=hash_password("Pass@1234"), role="student", name="Jane Smith"),
        ]
    db.add_all(users)
    db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="Student Result Management Portal", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # empty = same-origin only (frontend is served by this app)
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/", include_in_schema=False)
def serve_frontend():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))


@app.get("/health")
def health():
    return {"status": "OK"}


# ---------------------------------------------------------------- auth
@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Public self-registration is for students only (user_id = roll number)."""
    if db.query(User).filter(User.user_id == body.user_id).first():
        raise HTTPException(409, "This roll number is already registered")
    user = User(
        user_id=body.user_id, name=body.name.strip(), role="student", password=hash_password(body.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=TokenOut)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == body.user_id, User.role == body.role).first()
    ok = verify_password(body.password, user.password if user else _DUMMY_HASH)
    db.add(LoginLog(user_id=body.user_id, role=body.role, success=bool(user and ok and user.is_active)))
    db.commit()
    if not user or not ok or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return TokenOut(access_token=create_token(user), user=UserOut.model_validate(user))


@app.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


# ---------------------------------------------------------------- results
@app.get("/results/student/{roll}", response_model=List[ResultOut])
def student_results(roll: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    can_access_student(user, roll)
    rows = db.query(Result).filter(Result.student_roll == roll).order_by(Result.subject).all()
    return [result_out(r) for r in rows]


@app.get("/results/all", response_model=List[ResultOut])
def all_results(user: User = Depends(require_roles("teacher", "admin")), db: Session = Depends(get_db)):
    rows = db.query(Result).order_by(Result.student_roll, Result.subject).all()
    return [result_out(r) for r in rows]


def _student_or_404(db: Session, roll: str) -> User:
    s = db.query(User).filter(User.user_id == roll, User.role == "student").first()
    if not s:
        raise HTTPException(404, f"No registered student with roll number '{roll}'")
    return s


@app.post("/results", response_model=ResultOut)
def upsert_result(body: ResultIn, user: User = Depends(require_roles("teacher")), db: Session = Depends(get_db)):
    student = _student_or_404(db, body.student_roll)
    row = db.query(Result).filter(
        Result.student_roll == body.student_roll, Result.subject == body.subject.strip()
    ).first()
    if row:
        row.marks = body.marks
        row.student_name = student.name
    else:
        row = Result(
            student_roll=body.student_roll, student_name=student.name,
            subject=body.subject.strip(), marks=body.marks,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return result_out(row)


@app.delete("/results/{result_id}")
def delete_result(result_id: int, user: User = Depends(require_roles("teacher")), db: Session = Depends(get_db)):
    row = db.get(Result, result_id)
    if not row:
        raise HTTPException(404, "Result not found")
    db.delete(row)
    db.commit()
    return {"message": "Result deleted"}


# ---------------------------------------------------------------- topic results
@app.post("/topic-results", response_model=TopicOut)
def upsert_topic(body: TopicIn, user: User = Depends(require_roles("teacher")), db: Session = Depends(get_db)):
    if body.marks > body.max_marks:
        raise HTTPException(422, "Marks cannot exceed max marks")
    _student_or_404(db, body.student_roll)
    row = db.query(TopicResult).filter(
        TopicResult.student_roll == body.student_roll,
        TopicResult.subject == body.subject.strip(),
        TopicResult.topic == body.topic.strip(),
    ).first()
    if row:
        row.marks, row.max_marks = body.marks, body.max_marks
    else:
        row = TopicResult(
            student_roll=body.student_roll, subject=body.subject.strip(),
            topic=body.topic.strip(), marks=body.marks, max_marks=body.max_marks,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.get("/topic-results/student/{roll}", response_model=List[TopicOut])
def student_topics(roll: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    can_access_student(user, roll)
    return db.query(TopicResult).filter(TopicResult.student_roll == roll).all()


# ---------------------------------------------------------------- AI
# Plain `def` endpoint: FastAPI runs it in a worker thread, so the slow LLM call
# does not block the event loop.
@app.get("/ai/recommendations/{roll}")
def recommendations(roll: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    can_access_student(user, roll)
    rows = db.query(TopicResult).filter(TopicResult.student_roll == roll).all()
    if not rows:
        return {"weak_areas": [], "recommendation": "No topic-wise results found yet."}
    data = [{"subject": t.subject, "topic": t.topic, "marks": t.marks, "max_marks": t.max_marks} for t in rows]
    weak = detect_weak_topics(data)
    return {"weak_areas": weak, "recommendation": generate_recommendation(roll, weak)}


# ---------------------------------------------------------------- admin
@app.get("/admin/login-logs", response_model=List[LogOut])
def login_logs(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    return db.query(LoginLog).order_by(LoginLog.login_time.desc()).limit(50).all()


@app.get("/admin/users", response_model=List[UserOut])
def list_users(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    return db.query(User).order_by(User.role, User.user_id).all()


@app.post("/admin/users", response_model=UserOut, status_code=201)
def create_user(body: AdminCreateUser, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    if db.query(User).filter(User.user_id == body.user_id).first():
        raise HTTPException(409, "User ID already exists")
    new = User(user_id=body.user_id, name=body.name.strip(), role=body.role, password=hash_password(body.password))
    db.add(new)
    db.commit()
    db.refresh(new)
    return new


@app.delete("/admin/users/{uid}")
def delete_user(uid: int, user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    target = db.get(User, uid)
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == user.id:
        raise HTTPException(400, "You cannot delete your own account")
    db.delete(target)
    db.commit()
    return {"message": "User deleted"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))