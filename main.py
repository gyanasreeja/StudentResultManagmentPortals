from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import hashlib
from fastapi.responses import FileResponse
import os
from ai_recommend import detect_weak_topics, generate_recommendation

# Database Configuration
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgre123@127.0.0.1:5432/student_portal_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# FastAPI App
app = FastAPI(title="Student Result Management Portal")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Database Models
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String)  # student, teacher, admin
    name = Column(String)


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    student_roll = Column(String, index=True)
    student_name = Column(String)
    subject = Column(String)
    marks = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TopicResult(Base):
    __tablename__ = "topic_results"

    id = Column(Integer, primary_key=True, index=True)
    student_roll = Column(String, index=True)
    subject = Column(String)
    topic = Column(String)
    marks = Column(Float)
    max_marks = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    

class LoginLog(Base):
    __tablename__ = "login_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String)
    role = Column(String)
    login_time = Column(DateTime, default=datetime.utcnow)


# Create tables
Base.metadata.create_all(bind=engine)


# Pydantic Models
class UserLogin(BaseModel):
    user_id: str
    password: str
    role: str


class ResultCreate(BaseModel):
    student_roll: str
    student_name: str
    subject: str
    marks: float
class TopicResultCreate(BaseModel):
    student_roll: str
    subject: str
    topic: str
    marks: float
    max_marks: float


class TopicResultResponse(BaseModel):
    id: int
    student_roll: str
    subject: str
    topic: str
    marks: float
    max_marks: float
    created_at: datetime    


class ResultUpdate(BaseModel):
    student_name: Optional[str] = None
    subject: Optional[str] = None
    marks: Optional[float] = None


class UserResponse(BaseModel):
    id: int
    user_id: str
    role: str
    name: str


class ResultResponse(BaseModel):
    id: int
    student_roll: str
    student_name: str
    subject: str
    marks: float
    created_at: datetime


class LoginLogResponse(BaseModel):
    user_id: str
    role: str
    login_time: datetime


# Database Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Utility Functions
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed_password: str) -> bool:
    return hash_password(password) == hashed_password


# Initialize default users
def init_default_users(db: Session):
    if db.query(User).count() == 0:
        default_users = [
            User(user_id="S001", password=hash_password("pass123"), role="student", name="John Doe"),
            User(user_id="S002", password=hash_password("pass123"), role="student", name="Jane Smith"),
            User(user_id="T001", password=hash_password("teach123"), role="teacher", name="Prof. Johnson"),
            User(user_id="A001", password=hash_password("admin123"), role="admin", name="Admin User"),
        ]
        db.add_all(default_users)
        db.commit()
@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))


# API Endpoints
@app.on_event("startup")
async def startup_event():
    db = SessionLocal()
    init_default_users(db)
    db.close()


@app.post("/login")
async def login(user_login: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.user_id == user_login.user_id,
        User.role == user_login.role
    ).first()

    if not user or not verify_password(user_login.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    login_log = LoginLog(user_id=user.user_id, role=user.role)
    db.add(login_log)
    db.commit()

    return {
        "message": "Login successful",
        "user": UserResponse(
            id=user.id,
            user_id=user.user_id,
            role=user.role,
            name=user.name
        )
    }


@app.get("/results/student/{student_roll}", response_model=List[ResultResponse])
async def get_student_results(student_roll: str, db: Session = Depends(get_db)):
    results = db.query(Result).filter(Result.student_roll == student_roll).all()
    return results


@app.get("/results/all", response_model=List[ResultResponse])
async def get_all_results(db: Session = Depends(get_db)):
    results = db.query(Result).all()
    return results
@app.post("/topic-results", response_model=TopicResultResponse)
async def create_topic_result(result: TopicResultCreate, db: Session = Depends(get_db)):
    existing = db.query(TopicResult).filter(
        TopicResult.student_roll == result.student_roll,
        TopicResult.subject == result.subject,
        TopicResult.topic == result.topic
    ).first()

    if existing:
        existing.marks = result.marks
        existing.max_marks = result.max_marks
        db.commit()
        db.refresh(existing)
        return existing
    else:
        db_result = TopicResult(**result.dict())
        db.add(db_result)
        db.commit()
        db.refresh(db_result)
        return db_result


@app.get("/topic-results/student/{student_roll}", response_model=List[TopicResultResponse])
async def get_student_topic_results(student_roll: str, db: Session = Depends(get_db)):
    results = db.query(TopicResult).filter(TopicResult.student_roll == student_roll).all()
    return results


@app.get("/topic-results/all", response_model=List[TopicResultResponse])
async def get_all_topic_results(db: Session = Depends(get_db)):
    results = db.query(TopicResult).all()
    return results


@app.post("/results", response_model=ResultResponse)
async def create_result(result: ResultCreate, db: Session = Depends(get_db)):
    existing = db.query(Result).filter(
        Result.student_roll == result.student_roll,
        Result.subject == result.subject
    ).first()

    if existing:
        existing.marks = result.marks
        existing.student_name = result.student_name
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        db_result = Result(**result.dict())
        db.add(db_result)
        db.commit()
        db.refresh(db_result)
        return db_result


@app.delete("/results/{result_id}")
async def delete_result(result_id: int, db: Session = Depends(get_db)):
    db_result = db.query(Result).filter(Result.id == result_id).first()
    if not db_result:
        raise HTTPException(status_code=404, detail="Result not found")

    db.delete(db_result)
    db.commit()
    return {"message": "Result deleted successfully"}


@app.get("/admin/login-logs", response_model=List[LoginLogResponse])
async def get_login_logs(db: Session = Depends(get_db)):
    logs = db.query(LoginLog).order_by(LoginLog.login_time.desc()).limit(50).all()
    return logs


@app.get("/health")
async def health_check():
    return {"status": "OK", "message": "Student Result Management Portal API"}

@app.get("/ai/recommendations/{student_roll}")
async def get_recommendations(student_roll: str, db: Session = Depends(get_db)):
    topic_results = db.query(TopicResult).filter(TopicResult.student_roll == student_roll).all()
    if not topic_results:
        return {"weak_areas": [], "recommendation": "No topic-wise results found yet."}

    results_data = [
        {"subject": t.subject, "topic": t.topic, "marks": t.marks, "max_marks": t.max_marks}
        for t in topic_results
    ]
    weak_areas = detect_weak_topics(results_data)
    recommendation = generate_recommendation(student_roll, weak_areas)

    return {"weak_areas": weak_areas, "recommendation": recommendation}



if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
    