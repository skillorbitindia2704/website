import unittest
import os
import sys
# Path manipulation to ensure parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from datetime import datetime, timedelta
from flask import session
from app import create_app
from models import db
from models.user import User, AdminActivityLog
from models.store import Product, Order, OrderItem, PaymentAuditLog
from models.course import Course, Enrollment
from models.lms import LmsQuiz, QuizAttempt, RecordedSession
from extensions import bcrypt

class SkillOrbitHardeningTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        os.environ["FLASK_ENV"] = "testing"
        os.environ["SECRET_KEY"] = "super-secret-test-key"
        # Use an in-memory SQLite database for fast isolated tests
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        # Build fresh tables
        db.create_all()
        
        # Seed test records
        self._seed_test_data()
        
    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        
    def _seed_test_data(self):
        # Seed users
        password_hash = bcrypt.generate_password_hash("password123").decode("utf-8")
        
        # 1. Standard Student
        self.student = User(
            full_name="Alice Student",
            email="alice@test.com",
            password_hash=password_hash,
            role="student",
            is_approved=True
        )
        # 2. Administrator
        self.admin = User(
            full_name="Bob Admin",
            email="bob@test.com",
            password_hash=password_hash,
            role="admin",
            is_admin=True,
            is_approved=True
        )
        # 3. Teacher
        self.teacher = User(
            full_name="Charlie Teacher",
            email="charlie@test.com",
            password_hash=password_hash,
            role="teacher",
            is_approved=True
        )
        
        db.session.add(self.student)
        db.session.add(self.admin)
        db.session.add(self.teacher)
        db.session.commit()
        
    def test_security_headers(self):
        """Phase 1: Test security headers presence and values."""
        response = self.client.get("/")
        self.assertEqual(response.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-XSS-Protection"), "1; mode=block")
        self.assertEqual(response.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertIn("Permissions-Policy", response.headers)
        self.assertIn("Content-Security-Policy", response.headers)
        self.assertIn("X-Request-ID", response.headers)
        
    def test_account_lockout_mechanism(self):
        """Phase 1: Validate account lockout limits failed logins and locks out correctly."""
        # Check standard state
        self.assertEqual(self.student.failed_login_attempts, 0)
        self.assertIsNone(self.student.locked_until)
        
        # Send 4 incorrect login attempts
        for _ in range(4):
            response = self.client.post("/login", data={
                "email": "alice@test.com",
                "password": "wrong_password"
            })
            
        # Re-fetch user from DB
        db.session.refresh(self.student)
        self.assertEqual(self.student.failed_login_attempts, 4)
        self.assertIsNone(self.student.locked_until)
        
        # 5th failed attempt triggers lockout
        self.client.post("/login", data={
            "email": "alice@test.com",
            "password": "wrong_password"
        })
        
        db.session.refresh(self.student)
        self.assertEqual(self.student.failed_login_attempts, 5)
        self.assertIsNotNone(self.student.locked_until)
        self.assertTrue(self.student.locked_until > datetime.utcnow())
        
        # Attempt to login with the CORRECT password while locked
        response = self.client.post("/login", data={
            "email": "alice@test.com",
            "password": "password123"
        }, follow_redirects=True)
        self.assertIn(b"locked", response.data.lower() or b"")
        
    def test_strict_db_role_validation(self):
        """Phase 5: Validate that admin endpoints strictly verify role state in DB."""
        # First login as student
        self.client.post("/login", data={
            "email": "alice@test.com",
            "password": "password123"
        })
        
        # Attempt to access admin dashboard -> should be Denied
        response = self.client.get("/admin/dashboard", follow_redirects=True)
        self.assertIn(b"access denied", response.data.lower())
        
        # Log out
        self.client.get("/logout")
        
        # Login as admin
        self.client.post("/login", data={
            "email": "bob@test.com",
            "password": "password123"
        })
        
        # Access admin dashboard -> should succeed (returns index template elements)
        response = self.client.get("/admin/dashboard")
        self.assertEqual(response.status_code, 200)
        
    def test_admin_activity_logger(self):
        """Phase 5: Validate admin action activity logging after modifying database."""
        # Login as admin
        self.client.post("/login", data={
            "email": "bob@test.com",
            "password": "password123"
        })
        
        # Verify no activity logs currently exist
        self.assertEqual(AdminActivityLog.query.count(), 0)
        
        # Perform administrative POST action (e.g., create a product)
        response = self.client.post("/admin/products", data={
            "name": "Robotics Shield v3",
            "description": "High current motor driver shield",
            "price_inr": "1299",
            "stock": "45",
            "category": "Robotics",
            "rating": "4.8"
        }, follow_redirects=True)
        
        # Assert log was generated in target table
        logs = AdminActivityLog.query.all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].admin_id, self.admin.id)
        self.assertEqual(logs[0].action_type, "create")
        self.assertEqual(logs[0].target_table, "product")
        self.assertIn("Robotics Shield", logs[0].details)
        
    def test_secure_video_streaming(self):
        """Phase 4: Stream verification checks user enrollment permission."""
        # Add course & recorded lecture
        course = Course(
            title="Robotics for Beginners",
            video_url="https://youtube.com/mock"
        )
        db.session.add(course)
        db.session.commit()
        
        # Create a mock video file on disk for streaming testing
        dummy_video_path = os.path.join(self.app.root_path, "dummy_lecture.mp4")
        with open(dummy_video_path, "wb") as f:
            f.write(b"MP4HEADER\x00\x00\x00\x10ftypisom\x00\x00\x02\x00" + b"X" * 1024)
            
        lecture = RecordedSession(
            course_id=course.id,
            title="Introduction to Microcontrollers",
            video_path="dummy_lecture.mp4"
        )
        db.session.add(lecture)
        db.session.commit()
        
        try:
            # 1. Unauthenticated user request to stream -> Redirects to login
            r1 = self.client.get(f"/courses/stream/{lecture.id}")
            self.assertEqual(r1.status_code, 302)
            r1.close()
            
            # 2. Login as student (without enrollment) -> Denied
            self.client.post("/login", data={
                "email": "alice@test.com",
                "password": "password123"
            })
            r2 = self.client.get(f"/courses/stream/{lecture.id}")
            self.assertEqual(r2.status_code, 403)
            r2.close()
            
            # 3. Access as Admin -> Allowed (returns range request headers)
            self.client.get("/logout")
            self.client.post("/login", data={
                "email": "bob@test.com",
                "password": "password123"
            })
            r3 = self.client.get(f"/courses/stream/{lecture.id}", headers={"Range": "bytes=0-100"})
            self.assertEqual(r3.status_code, 206)
            self.assertEqual(r3.headers.get("Accept-Ranges"), "bytes")
            self.assertIn("Content-Range", r3.headers)
            r3.close()
            
        finally:
            # Clean up dummy file with exception handling for Windows file locks
            try:
                if os.path.exists(dummy_video_path):
                    os.remove(dummy_video_path)
            except Exception:
                pass
                
    def test_timed_quiz_timeout_prevention(self):
        """Phase 4: Timed quiz rejects rapid submissions & timing abuses."""
        # Create Course record first
        course = Course(
            id=1,
            title="Robotics for Beginners",
            video_url="https://youtube.com/mock"
        )
        db.session.add(course)
        db.session.commit()

        # Enroll student in course
        enrollment = Enrollment(
            user_id=self.student.id,
            course_id=1,
            is_paid=True,
            progress_pct=0
        )
        db.session.add(enrollment)
        db.session.commit()

        # Create an LMS Quiz
        quiz = LmsQuiz(
            course_id=1,
            title="Robotics Quiz 1",
            time_limit_seconds=60, # 1 minute
            pass_percent=60,
            questions_json=[
                {"question": "Is Arduino an MCU?", "options": ["Yes", "No"], "correctAnswer": "Yes"},
                {"question": "Is Raspberry Pi a microcomputer?", "options": ["Yes", "No"], "correctAnswer": "Yes"}
            ]
        )
        db.session.add(quiz)
        db.session.commit()
        
        # Login as student
        self.client.post("/login", data={
            "email": "alice@test.com",
            "password": "password123"
        })
        
        # 1. Access quiz learn page to seed start time session variable
        self.client.get("/courses/learn/1")
        
        # 2. Simulate ridiculously fast submission (suspicious rapid action, < 2s)
        # We manually overwrite session quiz_start_time to make it look like 0 seconds elapsed
        with self.client.session_transaction() as sess:
            sess[f"quiz_start_time_{quiz.id}"] = datetime.utcnow().timestamp()
            
        response = self.client.post("/courses/learn/1", data={
            "action": "quiz_lms",
            "quiz_id": str(quiz.id),
            "lq_1_0": "Yes",
            "lq_1_1": "Yes"
        }, follow_redirects=True)
        self.assertIn(b"rejected due to suspected rapid timing abuse", response.data)
        
        # 3. Simulate timed out submission (> limit + 15s latency window)
        with self.client.session_transaction() as sess:
            sess[f"quiz_start_time_{quiz.id}"] = datetime.utcnow().timestamp() - 120 # 2 minutes ago
            
        response = self.client.post("/courses/learn/1", data={
            "action": "quiz_lms",
            "quiz_id": str(quiz.id),
            "lq_1_0": "Yes",
            "lq_1_1": "Yes"
        }, follow_redirects=True)
        self.assertIn(b"time limit exceeded", response.data)
        
        # Verify timed out quiz attempt was logged as failed
        attempt = QuizAttempt.query.filter_by(user_id=self.student.id, quiz_id=quiz.id).first()
        self.assertIsNotNone(attempt)
        self.assertFalse(attempt.passed)
        self.assertEqual(attempt.score, 0)
        
    def test_duplicate_payment_prevention(self):
        """Phase 3: Prevent duplicate capturing of captured payments."""
        # Create an Order
        order = Order(
            user_id=self.student.id,
            total_inr=1500,
            payment_status="payment_pending",
            razorpay_order_id="order_dummy123"
        )
        db.session.add(order)
        db.session.commit()
        
        # Login as student
        self.client.post("/login", data={
            "email": "alice@test.com",
            "password": "password123"
        })
        
        # Mock payment verification function inside store route (using verify-payment endpoint)
        # 1. Verify first captures successfully (using signature validation bypass in testing/dev modes or mock)
        # Note: Since the test runs in 'testing' mode, verify_razorpay_signature will be bypassed or we simulate
        # standard transaction state by adding PaymentAuditLog
        
        # Simulate payment captured once
        order.payment_status = "paid"
        order.razorpay_payment_id = "pay_dummy_first"
        db.session.commit()
        
        # 2. Attempt duplicate verify request
        response = self.client.post(f"/store/verify-payment/{order.id}", data={
            "razorpay_order_id": "order_dummy123",
            "razorpay_payment_id": "pay_dummy_first",
            "razorpay_signature": "sig_dummy"
        }, follow_redirects=True)
        
        self.assertIn(b"already been verified", response.data)
        
        # Assert PaymentAuditLog has logged the capture attempt details
        audit_records = PaymentAuditLog.query.filter_by(order_id=order.id).all()
        self.assertTrue(len(audit_records) >= 1)
        self.assertIn("already paid", audit_records[0].message)

if __name__ == "__main__":
    unittest.main()
