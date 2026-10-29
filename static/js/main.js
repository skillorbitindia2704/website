(function () {
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

  function csrfToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  }

  function showToast(message, type = "info") {
    const root = $("#toast-root");
    if (!root || !message) return;
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = message;
    root.appendChild(el);
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transform = "translateX(12px)";
      setTimeout(() => el.remove(), 300);
    }, 4200);
  }

  /* Skip link: move focus into main for keyboard users */
  const skip = $(".skip-link");
  const mainEl = $("#main-content");
  skip?.addEventListener("click", (e) => {
    if (!mainEl) return;
    e.preventDefault();
    mainEl.focus({ preventScroll: false });
    mainEl.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  /* Page loader */
  window.addEventListener("load", () => {
    const pl = $("#page-loader");
    if (pl) pl.classList.add("done");
  });

  /* Theme */
  function updateLogoTheme(theme) {
    const logoImgs = $$(".nav-logo-img, .footer-logo-img");
    logoImgs.forEach((logoImg) => {
      const lightSrc = logoImg.getAttribute("data-light-src");
      const darkSrc = logoImg.getAttribute("data-dark-src");
      if (theme === "dark" && darkSrc) {
        logoImg.src = darkSrc;
      } else if (lightSrc) {
        logoImg.src = lightSrc;
      }
    });
  }

  // Storage can be unavailable in restricted/private browser contexts.
  // Never let a storage exception stop the rest of the site's interactions.
  let storedTheme = null;
  try {
    storedTheme = localStorage.getItem("soi-theme");
  } catch {
    /* Continue with the default theme when storage is unavailable. */
  }
  if (storedTheme === "dark" || storedTheme === "light") {
    document.documentElement.setAttribute("data-theme", storedTheme);
    updateLogoTheme(storedTheme);
  }
  $("#theme-toggle")?.addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme") || "light";
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("soi-theme", next);
    } catch {
      /* Theme still changes for the current page if storage is unavailable. */
    }
    updateLogoTheme(next);
  });

  /* Mobile nav */
  const navToggle = $("#nav-toggle");
  const navLinks = $("#nav-links");

  function closeMobileNav() {
    if (!navLinks || !navToggle) return;
    navLinks.classList.remove("open");
    navToggle.setAttribute("aria-expanded", "false");
    navToggle.classList.remove("is-open");
    document.body.classList.remove("nav-open");
  }

  navToggle?.addEventListener("click", () => {
    const open = navLinks.classList.toggle("open");
    navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    navToggle.classList.toggle("is-open", open);
    document.body.classList.toggle("nav-open", open);
  });

  // Close when clicking outside
  document.addEventListener("click", (e) => {
    if (!navLinks || !navToggle) return;
    if (!navLinks.classList.contains("open")) return;
    if (navLinks.contains(e.target) || navToggle.contains(e.target)) return;
    closeMobileNav();
  });

  // Close when clicking links in drawer on mobile
  $$("#nav-links a").forEach((a) => {
    a.addEventListener("click", () => {
      if (window.innerWidth <= 1024) {
        closeMobileNav();
      }
    });
  });

  // Close on screen resize above breakpoint
  window.addEventListener("resize", () => {
    if (window.innerWidth > 1024 && navLinks?.classList.contains("open")) {
      closeMobileNav();
    }
  });

  /* Auto-wrap unwrapped tables for responsive horizontal scrolling */
  function ensureResponsiveTables() {
    $$("table").forEach((table) => {
      const parent = table.parentElement;
      if (!parent) return;
      if (!parent.classList.contains("table-wrap") && !parent.classList.contains("table-responsive")) {
        const wrapper = document.createElement("div");
        wrapper.className = "table-wrap";
        parent.insertBefore(wrapper, table);
        wrapper.appendChild(table);
      }
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ensureResponsiveTables);
  } else {
    ensureResponsiveTables();
  }

  /* Flask flash → toasts */
  const flashEl = $("#flash-data");
  if (flashEl && flashEl.textContent.trim()) {
    try {
      const rows = JSON.parse(flashEl.textContent);
      rows.forEach((row) => {
        const [cat, msg] = row;
        if (msg) showToast(msg, cat === "danger" ? "error" : cat || "info");
      });
    } catch {
      /* ignore */
    }
    flashEl.remove();
  }

  /* Form double-submit */
  $$("form").forEach((form) => {
    form.addEventListener("submit", () => {
      const btn = form.querySelector("button[type='submit']");
      if (btn) {
        btn.disabled = true;
        btn.setAttribute("aria-busy", "true");
      }
    });
  });

  /* Scroll: navbar glass emphasis */
  const navWrap = document.getElementById("site-nav");
  if (navWrap) {
    const onNavScroll = () => {
      navWrap.classList.toggle("is-scrolled", window.scrollY > 16);
    };
    onNavScroll();
    window.addEventListener("scroll", onNavScroll, { passive: true });
  }

  /* Numeric counters [data-count-up="123"] optional suffix in sibling text */
  const countEls = document.querySelectorAll("[data-count-up]");
  if (countEls.length && "IntersectionObserver" in window) {
    const animate = (el) => {
      const raw = el.getAttribute("data-count-up");
      const target = parseInt(raw || "0", 10);
      if (Number.isNaN(target)) return;
      const dur = 1400;
      const t0 = performance.now();
      const step = (now) => {
        const p = Math.min(1, (now - t0) / dur);
        const eased = 1 - Math.pow(1 - p, 3);
        el.textContent = String(Math.round(target * eased));
        if (p < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    };
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (!e.isIntersecting) return;
          animate(e.target);
          io.unobserve(e.target);
        });
      },
      { threshold: 0.2 }
    );
    countEls.forEach((el) => io.observe(el));
  }

  /* Carousel */
  $$(".carousel-section").forEach((section) => {
    const track = $(".carousel", section);
    const prev = $('[data-carousel-prev]', section);
    const next = $('[data-carousel-next]', section);
    if (!track) return;
    const step = () => Math.min(track.clientWidth * 0.85, 320);
    prev?.addEventListener("click", () => track.scrollBy({ left: -step(), behavior: "smooth" }));
    next?.addEventListener("click", () => track.scrollBy({ left: step(), behavior: "smooth" }));
  });

  /* Scroll reveal */
  const revealEls = $$(".reveal");
  if (revealEls.length && "IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("visible");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    revealEls.forEach((el) => io.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add("visible"));
  }

  /* Wishlist */
  const auth = document.body.getAttribute("data-auth") === "1";
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".wishlist-btn");
    if (!btn) return;
    e.preventDefault();
    if (!auth) {
      showToast("Log in to save items to your wishlist.", "warning");
      return;
    }
    const pid = btn.getAttribute("data-product-id");
    if (!pid) return;
    btn.disabled = true;
    try {
      const res = await fetch("/api/wishlist/toggle", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
        },
        body: JSON.stringify({ product_id: Number(pid) }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Request failed");
      btn.classList.toggle("active", data.in_wishlist);
      btn.setAttribute("aria-pressed", data.in_wishlist ? "true" : "false");
      const heartIcon = btn.querySelector("i");
      if (heartIcon) {
        heartIcon.className = data.in_wishlist ? "ri-heart-fill" : "ri-heart-line";
      }
      showToast(data.in_wishlist ? "Added to wishlist" : "Removed from wishlist", "success");
    } catch {
      showToast("Could not update wishlist.", "error");
    } finally {
      btn.disabled = false;
    }
  });

  /* Notifications dropdown */
  const notifBtn = $("#notif-btn");
  const notifDrop = $("#notif-dropdown");
  const notifList = $("#notif-list");
  const notifEmpty = $("#notif-empty");
  const notifDot = $("#notif-dot");

  async function loadNotifications() {
    if (!auth || !notifList) return;
    try {
      const res = await fetch("/api/notifications");
      if (!res.ok) return;
      const data = await res.json();
      notifList.innerHTML = "";
      if (!data.notifications.length) {
        notifEmpty?.classList.add("show");
      } else {
        notifEmpty?.classList.remove("show");
        data.notifications.forEach((n) => {
          const li = document.createElement("li");
          li.textContent = n.message;
          if (!n.is_read) li.classList.add("unread");
          li.style.cursor = "pointer";
          li.addEventListener("click", async () => {
            await fetch(`/api/notifications/${n.id}/read`, {
              method: "POST",
              headers: { "X-CSRFToken": csrfToken() },
            });
            li.classList.remove("unread");
            loadNotifications();
          });
          notifList.appendChild(li);
        });
      }
      if (notifDot) {
        notifDot.hidden = !data.unread_count;
      }
    } catch {
      /* ignore */
    }
  }

  notifBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    const wasOpen = notifDrop && !notifDrop.hidden;
    if (notifDrop) notifDrop.hidden = wasOpen;
    notifBtn.setAttribute("aria-expanded", wasOpen ? "false" : "true");
    if (!wasOpen) loadNotifications();
  });

  document.addEventListener("click", (e) => {
    if (!notifDrop || notifDrop.hidden) return;
    if (notifBtn?.contains(e.target) || notifDrop.contains(e.target)) return;
    notifDrop.hidden = true;
    notifBtn?.setAttribute("aria-expanded", "false");
  });

  if (auth) loadNotifications();

  /* Internship modal */
  const modal = $("#internship-modal");
  const modalTitle = $("#internship-modal-title");
  const modalForm = $("#internship-modal-form");
  const modalClose = $("#internship-modal-close");

  $$('[data-open-internship-modal]').forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-internship-id");
      const title = btn.getAttribute("data-internship-title") || "Apply";
      const programFee = Number(btn.getAttribute("data-program-fee") || "0");
      if (modalForm) modalForm.action = `/internships/apply/${id}`;
      if (modalTitle) modalTitle.textContent = title;
      const modalHelp = $("#internship-modal-help");
      const submitButton = modalForm?.querySelector('button[type="submit"]');
      if (programFee > 0) {
        if (modalHelp) modalHelp.textContent = `Upload your resume and continue to secure Razorpay checkout for the one-time ₹${programFee} program fee. Your application is submitted after payment verification.`;
        if (submitButton) submitButton.innerHTML = '<i class="ri-lock-line" aria-hidden="true"></i> Continue to Secure Payment';
      } else {
        if (modalHelp) modalHelp.textContent = "Upload your resume and optionally include a brief note for the evaluation team.";
        if (submitButton) submitButton.innerHTML = '<i class="ri-send-plane-fill" aria-hidden="true"></i> Submit Application';
      }
      modal?.classList.add("open");
    });
  });

  modalClose?.addEventListener("click", () => modal?.classList.remove("open"));
  modal?.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.remove("open");
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (modal?.classList.contains("open")) modal.classList.remove("open");
    if (notifDrop && !notifDrop.hidden) {
      notifDrop.hidden = true;
      notifBtn?.setAttribute("aria-expanded", "false");
    }
    if (navLinks?.classList.contains("open")) {
      closeMobileNav();
    }
  });
})();
