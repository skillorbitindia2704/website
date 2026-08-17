# Skill Orbit India

Production-ready Flask edtech platform with auth, ecommerce, courses, internships, certificates, and admin workflows.

## Stack
- Flask + Blueprints
- SQLite via SQLAlchemy
- Flask-Login + Flask-WTF + Flask-Bcrypt
- HTML, CSS, JavaScript
- Razorpay integration hook
- PDF certificates (ReportLab)

## Project Structure
- `app.py` - app factory and config
- `models/` - database models
- `routes/` - modular route blueprints
- `utils/` - helper utilities
- `templates/` - Jinja templates
- `static/` - css/js/uploads/certificates

## Setup
1. Create virtual env and activate it.
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Create `.env` from `.env.example`.
4. Run:
   - `python app.py`

## Main Features
- Auth: signup/login/logout, bcrypt passwords, profile editing
- Store: product catalog, cart, checkout, Razorpay order creation hook, order history
- Courses: listing, enrollment, lesson progress, quiz evaluation
- Certificates: PDF generation, unique certificate ID, public verification URL
- Internships: listing, apply with resume upload, admin approval
- Dashboard: profile snapshot, orders, courses, certificates, leaderboard
- Gamification: points + badges + leaderboard ranking
- Admin: create/edit/delete products, upload courses, manage users, internships + application status

## Security
- CSRF enabled globally
- Password hashing with bcrypt
- Login/session protection for private routes
- Input validation and sanitized uploads (file extension + secure filename)
- Size limit for uploads

## Database Schema (Core Relationships)
- `User` 1:N `Order`
- `Order` 1:N `OrderItem`
- `Product` 1:N `OrderItem`
- `User` M:N `Course` through `Enrollment`
- `User` 1:N `Certificate`; `Course` 1:N `Certificate`
- `Internship` 1:N `InternshipApplication`; `User` 1:N `InternshipApplication`

## Razorpay
- Add `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` in `.env`.
- Checkout creates Razorpay order when keys are configured.

## Deployment
- `wsgi.py` added for WSGI servers.
- `render.yaml` included for Render deployment.
- For AWS (EC2/Elastic Beanstalk), run `gunicorn wsgi:app` behind Nginx.
