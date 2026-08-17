# TODO — AI Lab Package Management System (Admin-Controlled)

## Step 1: Repo analysis (completed)
- Identified Flask app architecture, SQLAlchemy ORM, Flask-Login auth, admin guard (`admin_required`).
- Identified current AI Lab page: hardcoded `LAB_PACKAGES` in `routes/ai_lab.py` and rendering in `templates/ai_lab/index.html`.
- Identified inquiry flow: `routes/ai_lab.py` → `AILabInquiry` in `models/ai_lab_inquiry.py`.
- Identified existing admin inquiry page: `routes/admin.py` + `templates/admin/ai_lab_inquiries.html`.

## Step 2: Database model
- [ ] Add `models/ai_lab_package.py` with requested schema fields.
- [ ] Ensure JSON storage for `features[]` (features list stored as JSON string).

## Step 3: Public AI Lab rendering
- [ ] Update `routes/ai_lab.py` to fetch visible packages from DB ordered by `displayOrder`.
- [ ] Add safe fallback seeding from the existing hardcoded packages if DB is empty.
- [ ] Update inquiry POST validation to use DB packages (keep `undecided`).
- [ ] Ensure inquiry still stores `package_interest` without breaking existing DB rows.

## Step 4: Admin panel
- [ ] Add admin route(s) in `routes/admin.py` for CRUD + enable/disable + reorder.
- [ ] Create template `templates/admin/ai_lab_packages.html` with search/filter + edit UI + delete confirmation.

## Step 5: Admin APIs
- [ ] Add admin-protected API endpoints in `routes/api.py` for packages CRUD/toggle/reorder.

## Step 6: Inquiry integration improvement
- [ ] Ensure inquiry captures selected package identifier consistent with DB (backward compatible).
- [ ] Optionally display the selected package title on admin inquiry page (without breaking current fields).

## Step 7: App wiring & migrations
- [ ] Confirm new model is registered (db.create_all handles table creation).
- [ ] If needed, extend `utils/db_migrate.py` for SQLite compatibility.

## Step 8: Verification
- [ ] Run minimal smoke checks: AI lab page loads, inquiry form submits, admin inquiry page loads.
- [ ] Test admin package add/edit/delete/toggle/reorder via web UI.
- [ ] Test admin APIs with authentication.

