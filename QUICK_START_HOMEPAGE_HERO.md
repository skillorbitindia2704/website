# 🚀 HOMEPAGE HERO MANAGER - QUICK START (5 MIN)

## What's New?
The placeholder "Visuals can be uploaded from admin later" has been **replaced with a complete working system** for managing homepage visuals, heading, buttons, and statistics.

## For Admins - Get Started Now ✨

### Step 1: Database Setup (1 min)
When you first start the app, the system automatically creates the homepage hero record. No manual DB work needed!

### Step 2: Access Admin Panel (30 sec)
1. Go to: `http://localhost:5000/admin/` (or your production URL)
2. You'll see "Homepage hero manager" card under "Homepage events"
3. Click it to open the manager

### Step 3: Add Your Content (2 min)
Fill in these sections:

**🎯 Hero Section Content**
- Badge: "AI • Robotics • Electronics"
- Badge subtext: "India's learning orbit"
- Main heading: "Premium AI + Robotics Learning Platform"
- Description: Your hero paragraph text

**🔘 Buttons**
- Primary: "Explore Courses" → `/courses`
- Secondary: "Book Free Demo" → `/ai-lab#enquiry`
- Tertiary: "Watch Video" → `/courses`

**🤖 AI Lab Card**
- Card title: "AI & Robotics Lab Atmosphere"
- Card description: Your card text
- Feature 1: "Live Projects" → "Portfolio-ready builds"
- Feature 2: "Verified Certs" → "QR verification"

**📊 KPIs** (The 4 number boxes)
- 5000+ → Students
- 120+ → Workshops
- 50+ → Schools
- 24×7 → Support

### Step 4: Upload Images (1 min)
Click on each image upload zone and drag/drop or select files:
- **Hero Image**: Main background (recommended: 1200×600px)
- **AI Lab Image**: Card image on the right
- **Robotics Image** (optional): Supporting visual
- **Workshop Image** (optional): Supporting visual
- **Student Activity Image** (optional): Supporting visual

✅ Allowed formats: PNG, JPG, WebP, GIF

### Step 5: Publish (30 sec)
Two options:
- **Save Draft**: Test changes without going live
- **Publish Changes**: Make changes visible on homepage immediately ✨

## That's It! 🎉

Your homepage now displays all content **dynamically** from the admin panel. No more hardcoded text!

---

## For Developers

### What Happened Behind the Scenes?

**Created:**
- `models/homepage_hero.py` - Database model with all fields
- `templates/admin/homepage_hero.html` - Admin UI with upload forms
- Added routes to `routes/admin.py` - Handle CRUD operations
- Added endpoint to `routes/api.py` - Public API for homepage

**Updated:**
- `templates/home.html` - Loads data from `/api/homepage-hero` dynamically
- `app.py` - Imported the new model
- `templates/admin/index.html` - Added dashboard link

### Database Schema
```sql
CREATE TABLE homepage_hero (
  id INTEGER PRIMARY KEY,
  badge_text VARCHAR(120),
  badge_subtext VARCHAR(160),
  heading VARCHAR(255),
  description TEXT,
  primary_button_text VARCHAR(80),
  primary_button_link VARCHAR(255),
  secondary_button_text VARCHAR(80),
  secondary_button_link VARCHAR(255),
  tertiary_button_text VARCHAR(80),
  tertiary_button_link VARCHAR(255),
  hero_image VARCHAR(255),
  ai_lab_image VARCHAR(255),
  robotics_image VARCHAR(255),
  workshop_image VARCHAR(255),
  student_activity_image VARCHAR(255),
  ai_lab_card_title VARCHAR(160),
  ai_lab_card_description TEXT,
  card_feature_1_title VARCHAR(80),
  card_feature_1_desc VARCHAR(160),
  card_feature_2_title VARCHAR(80),
  card_feature_2_desc VARCHAR(160),
  kpi_1_label VARCHAR(60),
  kpi_1_text VARCHAR(60),
  kpi_2_label VARCHAR(60),
  kpi_2_text VARCHAR(60),
  kpi_3_label VARCHAR(60),
  kpi_3_text VARCHAR(60),
  kpi_4_label VARCHAR(60),
  kpi_4_text VARCHAR(60),
  is_published BOOLEAN DEFAULT TRUE,
  is_draft BOOLEAN DEFAULT FALSE,
  created_at DATETIME DEFAULT NOW(),
  updated_at DATETIME DEFAULT NOW(),
  published_at DATETIME
);
```

### API Endpoint
**GET** `/api/homepage-hero` (Public - no auth required)

Returns JSON with all published hero data:
```json
{
  "badge_text": "AI • Robotics • Electronics",
  "heading": "Premium AI + Robotics Learning Platform",
  "description": "...",
  "primary_button": { "text": "...", "link": "..." },
  "hero_image": "uploads/homepage/xxx.jpg",
  "ai_lab_card": { "title": "...", "images": { "main": "..." } },
  "kpis": [{ "label": "5000+", "text": "Students" }, ...],
  "is_published": true,
  "updated_at": "2026-05-21T10:30:00"
}
```

### Routes
- `GET /admin/homepage-hero` - Show form
- `POST /admin/homepage-hero` - Save content
- `POST /admin/homepage-hero/delete-image/<field>` - Delete image

### Frontend Integration
The homepage (`home.html`) has a `<script>` that:
1. Fetches from `/api/homepage-hero` on page load
2. Updates the hero section with dynamic data
3. Includes XSS protection (escapeHtml functions)
4. Falls back gracefully if no data exists

---

## Testing Checklist

- [ ] Access `/admin/homepage-hero` without errors
- [ ] Form loads with default values
- [ ] Can upload images (drag & drop works)
- [ ] Save Draft works (shows draft status)
- [ ] Publish Changes works (shows published status)
- [ ] Homepage reflects published changes
- [ ] Delete image button works
- [ ] Edit existing content works
- [ ] API endpoint `/api/homepage-hero` returns JSON
- [ ] Mobile/responsive design works

---

## File Locations

| File | Purpose |
|------|---------|
| `models/homepage_hero.py` | Database model |
| `routes/admin.py` | Admin routes (search for `homepage_hero`) |
| `routes/api.py` | API endpoint (search for `get_homepage_hero`) |
| `templates/admin/homepage_hero.html` | Admin UI form |
| `templates/admin/index.html` | Dashboard (has link) |
| `templates/home.html` | Homepage (has fetch script) |
| `static/uploads/homepage/` | Image storage |

---

## Next Steps (Optional Enhancements)

- Add image compression before upload
- Add image cropping tool
- Schedule publish for future dates
- Multiple hero variants for A/B testing
- Mobile-specific hero image
- Hero animation effects
- Analytics tracking for hero clicks
- Backup/version history

---

**Questions?** Check `HOMEPAGE_HERO_SETUP.md` for detailed documentation.

**Ready to go live!** 🚀✨
