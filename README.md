# Student Result Management Portal with AI Recommendations

A secure web portal where students, teachers and admins manage and view exam results. The system finds weak topics automatically, and an AI advisor (Groq Llama 3.3) writes a short, personalised study tip for each student.

**Live demo:**  https://studentresultmanagmentportals-08gb.onrender.com/
**Demo video:**  https://drive.google.com/file/d/1frls_sik0psuhIeKqR9oI0Q9sMdarUa-/view?usp=sharing

> The free Render plan sleeps after 15 minutes. The first load can take about a minute.

## Features
- Student registration and login with JWT tokens (60-minute expiry)
- Passwords hashed with bcrypt
- Role-based access control for student, teacher and admin
- Teachers add, update and delete subject marks and enter topic-wise marks
- Automatic grades (A+ to F), average and strongest subject
- AI study advice: topics below 60% are flagged, then the LLM writes a tip
- Admin dashboard: user management, password reset, statistics and login history (including failed attempts)
- Seed script for 456 demo students with marks

## Users and Access
| Role | Can do | Cannot do |
|---|---|---|
| Student | Register, view own results, grades and AI advice | See other students' data or change marks |
| Teacher | Add, update and delete results, add topic marks, view all results | Manage users or view login logs |
| Admin | Create, remove and reset users, view all results, stats and login logs | Edit marks |

Teachers and admins are created by an admin. Public registration creates students only.

## How It Works
1. A student registers, then logs in by choosing a role, an ID and a password.
2. The server checks the bcrypt hash and returns a JWT.
3. Every request is checked by role. Students can open only their own roll number.
4. A teacher saves subject marks and topic marks.
5. Topics below 60% are marked weak. The system finds matching study material and asks the LLM for a short tip.
6. The student dashboard shows results, grades, average and the AI advice.

## Tech Stack
- **Backend:** FastAPI, SQLAlchemy, PostgreSQL
- **Security:** bcrypt, PyJWT
- **AI:** LangChain, Groq (Llama 3.3)
- **Frontend:** HTML, CSS, JavaScript
- **Deployment:** Render

## Run Locally
1. Clone the repo and set up the environment:
   ```
   git clone https://github.com/gyanasreeja/StudentResultManagmentPortals.git
   cd StudentResultManagmentPortals
   python -m venv venv
   venv\Scripts\activate
   python -m pip install -r requirements.txt
   ```
2. Create a PostgreSQL database named `student_portal_db`.
3. Copy `.env.example` to `.env` and fill it in:
   ```
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/student_portal_db
   JWT_SECRET=a-long-random-string
   GROQ_API_KEY=your_groq_key
   ADMIN_PASSWORD=choose-a-strong-password
   SEED_DEMO=0
   ```
4. Start the app and open http://localhost:8000:
   ```
   python main.py
   ```
5. Optional demo data (students S001 to S456 with marks, and teachers T001 to T003):
   ```
   python seed_456.py
   ```

## Demo Logins (after running the seed)
| Role | ID | Password |
|---|---|---|
| Teacher | T001 | Teach@123 |
| Student | S001 | stud@123 |
| Admin | A001 | your ADMIN_PASSWORD |

Change these before using the app for real.

## API Overview
| Method | Endpoint | Access |
|---|---|---|
| POST | /auth/register | Public (students) |
| POST | /auth/login | Public |
| GET | /results/student/{roll} | Own roll, teacher, admin |
| GET | /results/all | Teacher, admin |
| POST, DELETE | /results | Teacher |
| POST | /topic-results | Teacher |
| GET | /ai/recommendations/{roll} | Own roll, teacher, admin |
| GET, POST | /admin/users | Admin |
| PUT | /admin/users/{id}/password | Admin |
| GET | /admin/login-logs | Admin |

Interactive API docs are at `/docs`.

## Security
- bcrypt password hashing and JWT bearer tokens
- Server-side role checks on every endpoint, with per-student data isolation
- Input validation with Pydantic
- Output escaping in the frontend to prevent XSS
- Secrets are kept in environment variables, and `.env` is not committed

## Author
Gyanasreeja Patnala

Frontend: http://localhost:3000 Backend API: http://localhost:8000 API Documentation: http://localhost:8000/docs
 <img width="1919" height="921" alt="image" src="https://github.com/user-attachments/assets/e01ee7a8-6dd2-43dc-9470-c5c87469e457" />
 <img width="1919" height="892" alt="image" src="https://github.com/user-attachments/assets/4895501e-be03-4799-8c20-6541453e1ec1" />
 <img width="1802" height="923" alt="image" src="https://github.com/user-attachments/assets/8f86bfdf-fe52-44a7-989a-732e8792585e" />
 <img width="1864" height="785" alt="image" src="https://github.com/user-attachments/assets/e4135ea2-bf1b-4084-9a67-e68a1815d736" />
 Admin Dash Board :
 <img width="1886" height="941" alt="image" src="https://github.com/user-attachments/assets/1e1648e5-c810-4096-9d57-7531d6e5b2bc" />
 Teacher Dash Board:
 <img width="1919" height="928" alt="image" src="https://github.com/user-attachments/assets/7d01a31c-4053-4e33-b8f6-b6c945b553e4" />







<img width="5929" height="6728" alt="diagram" src="https://github.com/user-attachments/assets/a17a9459-d464-485a-ab95-13041ab08135" />

