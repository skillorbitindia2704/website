- [x] Update base.html to include dynamic favicon + og:image
- [x] Update backend branding keys constants (app.py)
- [ ] Implement backend routes + helpers for logo/dark logo/favicon upload/delete and branding settings persistence

- [ ] Update navbar HTML to consume dynamic logo URLs (light/dark) (already done)
- [ ] Update base.html to include dynamic favicon + og:image (already done)
- [ ] Add admin dashboard card link to Website Branding (already done)
- [ ] Wire /admin/website-branding route to render website_branding.html with current saved URLs
- [ ] Add admin upload endpoint /admin/website-branding/upload (AJAX)
- [ ] Add admin delete endpoint /admin/website-branding/delete (AJAX)
- [ ] Validate server-side file type + size <= 5MB
- [ ] Save in static branding directory and persist paths in SiteSetting keys
- [ ] Ensure refresh updates favicon/head and navbar immediately (server-rendered)

