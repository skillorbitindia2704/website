# Flask Application Code Analysis Report
**Application:** Skill Orbit India (SOI_2026)  
**Date:** May 12, 2026  
**Scope:** Routes, Models, Utils, Templates

---

## EXECUTIVE SUMMARY

The application has **3 CRITICAL ISSUES** with broken URL redirects and **1 MISSING FEATURE**. The codebase is generally well-structured, but there are issues with endpoint references in templates and missing functionality.

---

## 1. ALL DEFINED ROUTES

### Blueprint: `main` (no prefix)
| Endpoint | Method | URL | Function |
|----------|--------|-----|----------|
| main.home | GET | / | home() |
| main.about | GET | /about | about() |

### Blueprint: `auth` (no prefix)
| Endpoint | Method | URL | Function |
|----------|--------|-----|----------|
| auth.signup | GET, POST | /signup | signup() |
| auth.login | GET, POST | /login | login() |
| auth.logout | GET | /logout | logout() |
| auth.profile | GET, POST | /profile | profile() |

### Blueprint: `store` (prefix: /store)
| Endpoint | Method | URL | Function |
|----------|--------|-----|----------|
| store.listing | GET | /store | listing() |
| store.add_to_cart | POST | /store/add-to-cart/<product_id> | add_to_cart() |
| store.view_cart | GET | /store/cart | view_cart() |
| store.checkout | POST | /store/checkout | checkout() |

### Blueprint: `courses` (prefix: /courses)
| Endpoint | Method | URL | Function |
|----------|--------|-----|----------|
| courses.list_courses | GET | /courses | list_courses() |
| courses.enroll | POST | /courses/enroll/<course_id> | enroll() |
| courses.buy_course | GET | /courses/buy/<course_id> | buy_course() |
| courses.verify_course_payment | POST | /courses/verify-payment/<course_id> | verify_course_payment() |
| courses.learn | GET, POST | /courses/learn/<course_id> | learn() |

### Blueprint: `certificates` (prefix: /certificate)
| Endpoint | Method | URL | Function |
|----------|--------|-----|----------|
| certificates.verify_lookup | GET, POST | /certificate/verify | verify_lookup() |
| certificates.verify | GET | /certificate/verify/<uid> | verify() |
| certificates.download | GET | /certificate/download/<uid> | download() |

### Blueprint: `internships` (prefix: /internships)
| Endpoint | Method | URL | Function |
|----------|--------|-----|----------|
| internships.listing | GET | /internships | listing() |
| internships.apply | POST | /internships/apply/<internship_id> | apply() |

### Blueprint: `it_services` (prefix: /it-services)
| Endpoint | Method | URL | Function |
|----------|--------|-----|----------|
| it_services.index | GET | /it-services | index() |
| it_services.submit_request | POST | /it-services/request | submit_request() |

### Blueprint: `ai_lab` (prefix: /ai-lab)
| Endpoint | Method | URL | Function |
|----------|--------|-----|----------|
| ai_lab.index | GET | /ai-lab | index() |
| ai_lab.inquiry | POST | /ai-lab/inquiry | inquiry() |

### Blueprint: `dashboard` (prefix: /dashboard)
| Endpoint | Method | URL | Function |
|----------|--------|-----|----------|
| dashboard.index | GET | /dashboard | index() |
| dashboard.orders | GET | /dashboard/orders | orders() |
| dashboard.my_courses | GET | /dashboard/courses | my_courses() |
| dashboard.certificates | GET | /dashboard/certificates | certificates() |

### Blueprint: `teacher` (prefix: /teacher)
| Endpoint | Method | URL | Function |
|----------|--------|-----|----------|
| teacher.dashboard | GET | /teacher/dashboard | dashboard() |
| teacher.create_course | GET, POST | /teacher/courses/new | create_course() |

### Blueprint: `student` (prefix: /student)
| Endpoint | Method | URL | Function |
|----------|--------|-----|----------|
| student.dashboard | GET | /student/dashboard | dashboard() |

### Blueprint: `admin` (prefix: /admin)
| Endpoint | Method | URL | Function |
|----------|--------|-----|----------|
| admin.index | GET | /admin / /admin/dashboard | index() |
| admin.products | GET, POST | /admin/products | products() |
| admin.delete_product | POST | /admin/products/<product_id>/delete | delete_product() |
| admin.edit_product | POST | /admin/products/<product_id>/edit | edit_product() |
| admin.orders | GET | /admin/orders | orders() |
| admin.update_order_status | POST | /admin/orders/<order_id>/status | update_order_status() |
| admin.courses | GET, POST | /admin/courses | courses() |
| admin.internships | GET, POST | /admin/internships | internships() |
| admin.update_application_status | POST | /admin/internship-application/<app_id>/status | update_application_status() |
| admin.users | GET | /admin/users | users() |
| admin.teachers | GET, POST | /admin/teachers | teachers() |
| admin.approve_teacher | POST | /admin/teachers/<user_id>/approve OR /admin/approve_teacher/<user_id> | approve_teacher() |
| admin.reject_teacher | POST | /admin/teachers/<user_id>/reject OR /admin/reject_teacher/<user_id> | reject_teacher() |
| admin.delete_teacher | POST | /admin/teachers/<user_id>/delete | delete_teacher() |
| admin.set_user_role | POST | /admin/users/<user_id>/role | set_user_role() |
| admin.service_requests | GET | /admin/service-requests OR /admin/services | service_requests() |
| admin.service_request_status | POST | /admin/service-requests/<rid>/status | service_request_status() |
| admin.ai_lab_inquiries | GET | /admin/ai-lab-inquiries OR /admin/ai-lab | ai_lab_inquiries() |
| admin.ai_lab_inquiry_status | POST | /admin/ai-lab-inquiries/<iid>/status | ai_lab_inquiry_status() |
| admin.issue_certificate | GET, POST | /admin/certificates | issue_certificate() |
| admin.cleanup_users | GET, POST | /admin/cleanup-users | cleanup_users() |

### Blueprint: `api` (prefix: /api)
| Endpoint | Method | URL | Function |
|----------|--------|-----|----------|
| api.list_notifications | GET | /api/notifications | list_notifications() |
| api.mark_notification_read | POST | /api/notifications/<nid>/read | mark_notification_read() |
| api.wishlist_toggle | POST | /api/wishlist/toggle | wishlist_toggle() |
| api.wishlist_ids | GET | /api/wishlist/ids | wishlist_ids() |
| api.list_products_api | GET | /api/products | list_products_api() |
| api.admin_orders | GET | /api/admin/orders | admin_orders() |
| api.admin_update_order | PUT | /api/admin/orders/<order_id> | admin_update_order() |

---

## 2. BROKEN url_for() CALLS - CRITICAL ISSUES

### ❌ ISSUE #1: Non-existent Blueprint Reference
**File:** [templates/courses/listing.html](templates/courses/listing.html#L35)  
**Line:** 35  
**Code:** `url_for('course_lms.overview', course_id=c.id)`  
**Problem:** Blueprint `course_lms` does not exist  
**Impact:** Link will crash with "BuildError: Could not build url for endpoint course_lms.overview"  
**Recommendation:** Change to `url_for('courses.learn', course_id=c.id)`

---

### ❌ ISSUE #2: Non-existent Endpoint
**File:** [templates/teacher/dashboard.html](templates/teacher/dashboard.html#L14)  
**Line:** 14  
**Code:** `url_for('teacher.teacher_courses')`  
**Problem:** Endpoint `teacher_courses` does not exist in teacher blueprint  
**Available Endpoints:** `teacher.dashboard`, `teacher.create_course`  
**Impact:** Link will crash with "BuildError: Could not build url for endpoint teacher.teacher_courses"  
**Recommendation:** Change to `url_for('teacher.dashboard')` or `url_for('teacher.create_course')`

---

### ❌ ISSUE #3: Non-existent Endpoint  
**File:** [templates/admin/index.html](templates/admin/index.html#L98)  
**Line:** 98  
**Code:** `url_for('admin.ai_lab_packages')`  
**Problem:** Endpoint `ai_lab_packages` does not exist in admin blueprint  
**Existing Endpoint:** `admin.ai_lab_inquiries` exists  
**Impact:** Link will crash with "BuildError: Could not build url for endpoint admin.ai_lab_packages"  
**Recommendation:** Change to `url_for('admin.ai_lab_inquiries')`

---

### ✅ All Other url_for() Calls - VALID
The following templates have **valid** url_for() references that match defined endpoints:
- templates/partials/navbar.html (17 calls - all valid)
- templates/partials/breadcrumbs.html (embedded in templates - all valid)
- templates/about.html (9 calls - all valid)
- templates/home.html (11 calls - all valid)
- templates/auth/*.html (all valid)
- templates/courses/payment.html (3 calls - all valid)
- templates/dashboard/*.html (all valid)
- templates/certificates/verify.html, verify_lookup.html (all valid)
- templates/admin/*.html (except #3 above - rest valid)
- templates/store/*.html (all valid)
- templates/internships/listing.html (all valid)
- templates/student/dashboard.html (all valid)

---

## 3. MISSING BLUEPRINT/ENDPOINTS

### ⚠️ Missing Feature: Course LMS/Learning Management System
**Referenced in:** [templates/courses/listing.html](templates/courses/listing.html#L35)  
**Missing Endpoint:** `course_lms.overview`  
**Current Status:** No blueprint named `course_lms` registered  
**Workaround:** Currently uses `courses.learn` which exists  
**Recommendation:** Either create `course_lms` blueprint or remove the reference

---

### ⚠️ Missing Feature: Teacher Courses View
**Referenced in:** [templates/teacher/dashboard.html](templates/teacher/dashboard.html#L14)  
**Missing Endpoint:** `teacher.teacher_courses`  
**Available Alternatives:** 
- `teacher.dashboard` - shows all courses
- `teacher.create_course` - form to create course  
**Recommendation:** Remove link or implement actual teacher courses list view

---

## 4. BLUEPRINT REGISTRATIONS - ALL VALID ✅

All blueprints are properly registered in [app.py](app.py):
```python
✅ app.register_blueprint(main_bp)
✅ app.register_blueprint(auth_bp)
✅ app.register_blueprint(store_bp, url_prefix="/store")
✅ app.register_blueprint(courses_bp, url_prefix="/courses")
✅ app.register_blueprint(cert_bp, url_prefix="/certificate")
✅ app.register_blueprint(internships_bp, url_prefix="/internships")
✅ app.register_blueprint(it_services_bp, url_prefix="/it-services")
✅ app.register_blueprint(ai_lab_bp, url_prefix="/ai-lab")
✅ app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
✅ app.register_blueprint(teacher_bp)
✅ app.register_blueprint(student_bp)
✅ app.register_blueprint(admin_bp, url_prefix="/admin")
✅ app.register_blueprint(api_bp)
```

---

## 5. IMPORTS - NO CIRCULAR DEPENDENCIES DETECTED ✅

Checked all Python files for circular imports:
- No circular import patterns found
- All imports are properly ordered
- Extensions initialized correctly before usage
- All blueprints import independently

**Models Import Chain:** `db (extensions) → models → (no circular references)`

---

## 6. BROKEN IMPORTS - ALL VALID ✅

All imports successfully resolve:
- ✅ Flask extensions (bcrypt, login_manager, csrf, db)
- ✅ All model imports in app.py
- ✅ All route imports in app.py  
- ✅ Utils imports (decorators, role_auth, certificates, payments, notifications)
- ✅ Third-party imports (email_validator, razorpay, reportlab, sqlalchemy)

---

## 7. DATABASE MODELS - ANALYSIS

### Model Structure ✅ VALID

**User Model** - [models/user.py](models/user.py)
- ✅ Proper relationships defined
- ✅ Cascade delete configured appropriately
- ✅ Admin flags sync correctly
- ✅ Badge update method exists
- ⚠️ WARNING: `update_badge()` queries other models inside the method - consider lazy loading issues

**Course Model** - [models/course.py](models/course.py)
- ✅ Extended teaching system with JSON fields (live_class, videos, notes, quiz)
- ✅ Relationships properly defined
- ⚠️ Uses JSON columns which may have compatibility issues with some databases

**Enrollment Model** - [models/course.py](models/course.py)
- ✅ Unique constraint on (user_id, course_id)
- ✅ Proper relationships and foreign keys

**Certificate Model** - [models/course.py](models/course.py)
- ✅ Unique certificate_uid indexed
- ✅ Proper relationships

**Order & OrderItem Models** - [models/store.py](models/store.py)
- ✅ Proper cascade delete
- ✅ All relationships valid

**All Other Models** - ✅ VALID
- Internship, InternshipApplication
- AILabInquiry  
- ServiceRequest
- Notification
- WishlistItem

---

## 8. FORM & TEMPLATE ISSUES

### Template Syntax - ALL VALID ✅

All Jinja2 template syntax is correct:
- ✅ Proper conditionals and loops
- ✅ Filters used correctly
- ✅ Breadcrumb variable passing valid
- ✅ Form handling correct

### Missing Template Variables - NONE FOUND ✅

All variables passed to templates are correctly populated in route handlers.

---

## 9. ADMIN DASHBOARD - ANALYSIS

### Features Present ✅
- User management
- Product/Store management
- Course management (basic admin upload)
- Teacher approval workflow
- Order status tracking
- Service request management
- AI Lab inquiry management
- Certificate issuance
- User cleanup utility

### Issues Found:
- 🔴 CRITICAL: Link to `admin.ai_lab_packages` endpoint breaks
- ⚠️ Duplicate route decorators on approve/reject teacher (alternative paths)

---

## 10. AUTHENTICATION FLOW - ANALYSIS

### Login Flow ✅ VALID
```
Unauthenticated → /login → Session set → Role-based redirect:
  - admin → admin.index
  - teacher → teacher.dashboard  
  - student → student.dashboard
```

### Signup Flow ✅ VALID
```
New user → /signup → Account created → Redirect to login
```

### Role-Based Access Control ✅ VALID
- ✅ admin_required decorator
- ✅ teacher_required decorator
- ✅ student_required decorator
- ✅ Proper redirect for unapproved teachers
- ✅ Session synchronization with Flask-Login

### Issue: Teacher Approval Alternate Routes
**Location:** [routes/admin.py](routes/admin.py#L327-L328)
- Function has dual decorators: `@admin_bp.post("/teachers/<int:user_id>/approve")` and `@admin_bp.post("/approve_teacher/<int:user_id>")`
- Creates two URL paths for same function
- Not a bug, but unusual design pattern

---

## 11. PAYMENT INTEGRATION

### Razorpay Integration ✅ VALID
- ✅ create_razorpay_order() function exists
- ✅ verify_razorpay_signature() function exists  
- ✅ Proper environment variable handling
- ✅ Fallback to COD if Razorpay not configured

### Issues:
- ⚠️ No error handling if Razorpay API calls timeout
- ⚠️ Signature verification failure doesn't indicate which validation failed

---

## 12. CERTIFICATE GENERATION ✅ VALID

- ✅ generate_certificate_pdf() creates PDFs correctly
- ✅ UUID generation for unique cert IDs
- ✅ Proper file path handling
- ✅ Certificate verification by UID works

---

## 13. NOTIFICATIONS SYSTEM ✅ VALID

- ✅ notify_user() helper exists
- ✅ Notifications model properly structured
- ✅ Cascade delete configured
- ✅ API endpoints for notification management exist

---

## SUMMARY OF ISSUES

### 🔴 CRITICAL (3)
1. Broken url_for() in courses/listing.html → course_lms.overview
2. Broken url_for() in teacher/dashboard.html → teacher.teacher_courses
3. Broken url_for() in admin/index.html → admin.ai_lab_packages

### ⚠️ WARNINGS (2)
1. Duplicate route paths for teacher approval (alternative routes)
2. User.update_badge() method has potential lazy-loading issues with queries inside method

### ℹ️ RECOMMENDATIONS (4)
1. Add missing course_lms blueprint or update reference
2. Add teacher.teacher_courses endpoint or remove dashboard link
3. Fix admin dashboard link for ai_lab_packages
4. Refactor User.update_badge() to avoid N+1 query problem

---

## FILE LOCATIONS REFERENCE

**Routes:** d:/SOI_2026/routes/  
**Models:** d:/SOI_2026/models/  
**Templates:** d:/SOI_2026/templates/  
**Utils:** d:/SOI_2026/utils/  
**Main App:** d:/SOI_2026/app.py
