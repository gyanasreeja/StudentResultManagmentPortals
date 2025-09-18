StudentResultManagmentPortal
A comprehensive web-based portal for managing student results with role-based authentication and secure access control. Built with modern technologies for educational institutions. ✨ Features 🔐 Role-Based Authentication

Students: View personal results only (secure access) Teachers: Full CRUD operations on all student results Admin: System oversight with login monitoring

🎯 Core Functionalities

Secure Login System with password hashing (SHA-256) Real-time Result Management with instant updates Responsive Design - works on all devices Login Activity Tracking for administrative oversight Grade Calculation with automatic letter grade assignment

🛡️ Security Features

Password hashing and validation Role-based access control (RBAC) Session management Data isolation (students can only see their own results) Login activity logging with timestamps

🚀 Tech Stack Frontend

HTML5 - Semantic markup Tailwind CSS - Modern utility-first styling JavaScript (ES6+) - Interactive functionality Responsive Design - Mobile-first approach

Backend

FastAPI - High-performance Python web framework PostgreSQL - Robust relational database SQLAlchemy - Python SQL toolkit and ORM Uvicorn - ASGI web server

Additional Tools

Pydantic - Data validation using Python type hints Hashlib - Secure password hashing CORS middleware - Cross-origin resource sharing HOME PAGE: image Student Dashboard image Teacher Dashboard image Admin DashBoard image Access the application

Frontend: http://localhost:3000 Backend API: http://localhost:8000 API Documentation: http://localhost:8000/docs

👥 Default Login Credentials Students

Roll Number: S001 | Password: pass123 Roll Number: S002 | Password: pass123

Teacher

Employee ID: T001 | Password: teach123

Admin

Admin ID: A001 | Password: admin123

🔧 API Endpoints Authentication

POST /login - User authentication for all roles

Student Routes

GET /results/student/{roll_number} - Get student's personal results Teacher Routes

GET /results/all - Get all student results POST /results - Add new result PUT /results/{result_id} - Update existing result DELETE /results/{result_id} - Delete result

Admin Routes

GET /admin/login-logs - View login activity logs GET /admin/users - View all system users

📊 Database Schema Users Table sqlCREATE TABLE users ( id SERIAL PRIMARY KEY, user_id VARCHAR(50) UNIQUE NOT NULL, password VARCHAR(255) NOT NULL, role VARCHAR(20) NOT NULL, name VARCHAR(100) NOT NULL ); Results Table sqlCREATE TABLE results ( id SERIAL PRIMARY KEY, student_roll VARCHAR(20) NOT NULL, student_name VARCHAR(100) NOT NULL, subject VARCHAR(100) NOT NULL, marks DECIMAL(5,2) NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ); Login Logs Table sqlCREATE TABLE login_logs ( id SERIAL PRIMARY KEY, user_id VARCHAR(50) NOT NULL, role VARCHAR(20) NOT NULL, login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ); 🎯 Use Cases For Educational Institutions

Schools - Manage student grades and results Colleges - Semester result management Training Centers - Course completion tracking Coaching Centers - Student performance monitoring

Key Benefits

Paperless System - Reduce manual paperwork Instant Access - Students get results immediately Secure Data - Role-based access ensures data privacy Audit Trail - Complete login and activity tracking Scalable - Handles multiple subjects and students

🔒 Security Considerations

Password Hashing: SHA-256 encryption for all passwords Role Validation: Server-side role verification for all endpoints Data Isolation: Students can only access their own data Input Validation: Comprehensive data validation using Pydantic SQL Injection Protection: SQLAlchemy ORM prevents SQL injection CORS Configuration: Controlled cross-origin resource sharing
