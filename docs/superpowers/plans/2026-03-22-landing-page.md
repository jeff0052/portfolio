# Landing Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Jeff's personal landing page — a cinematic, full-screen sectioned portfolio site with fade-in scroll animations.

**Architecture:** Single-page static site with 4 full-screen sections (Hero, About, Projects, Contact). CSS custom properties for design tokens, Intersection Observer for scroll-triggered animations, CSS scroll-snap for full-screen paging. Zero dependencies.

**Tech Stack:** Pure HTML, CSS, JavaScript. No frameworks, no build tools, no external fonts.

**Spec:** `docs/superpowers/specs/2026-03-22-landing-page-design.md`

---

## File Structure

```
landing-page/
├── index.html      — Semantic HTML structure, all 4 sections + nav
├── css/
│   └── style.css   — Design tokens, layout, animations, responsive
├── js/
│   └── main.js     — Intersection Observer, scroll behavior
└── assets/         — (empty for now, future images)
```

---

### Task 1: Project Scaffold + HTML Structure

**Files:**
- Create: `landing-page/index.html`
- Create: `landing-page/css/style.css` (empty placeholder)
- Create: `landing-page/js/main.js` (empty placeholder)

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p landing-page/css landing-page/js landing-page/assets
```

- [ ] **Step 2: Write index.html with full semantic structure**

Create `landing-page/index.html` with:
- `<!DOCTYPE html>`, charset, viewport meta
- Link to `css/style.css`, defer `js/main.js`
- `<nav>` — fixed top bar: logo "JEFF" left, anchor links (ABOUT, PROJECTS, CONTACT) right
- `<section id="hero">` — "HELLO, I'M" label, "JEFF" h1, "FOUNDER · BUILDER · CREATOR" subtitle, 3 decorative `<div class="geo-ring">` elements, 2 `<div class="geo-line">` elements, scroll indicator with "↓ SCROLL TO EXPLORE"
- `<section id="about">` — section number "01 / ABOUT", heading "Building the operating system for one-person companies", paragraph with Chinese intro text
- `<section id="projects">` — section number "02 / PROJECTS", 3 project cards each with: project name, description, arrow "→". Data: FounderOS (金), Onta Network (青), FocalPoint (紫)
- `<section id="contact">` — section number "03 / CONTACT", heading "Let's Connect", 3 capsule links: GitHub (github.com/jeff0052), Twitter (#), Email (#)
- All sections get `class="section"` and elements that animate get `class="fade-in"`

- [ ] **Step 3: Write empty CSS and JS placeholders**

`landing-page/css/style.css`: comment `/* Landing Page Styles */`
`landing-page/js/main.js`: comment `// Landing Page Scripts`

- [ ] **Step 4: Open in browser to verify raw HTML structure**

Open `landing-page/index.html` in browser. Verify all text content is visible (unstyled). All 4 sections present, nav links work as anchors.

- [ ] **Step 5: Commit**

```bash
git add landing-page/
git commit -m "feat: landing page HTML scaffold with all sections"
```

---

### Task 2: CSS Design Tokens + Base Layout

**Files:**
- Modify: `landing-page/css/style.css`

- [ ] **Step 1: Write CSS custom properties (design tokens)**

At top of `style.css`, define `:root` with:
```css
:root {
  /* Colors */
  --bg-hero: #0a0a0a;
  --bg-hero-mid: #1a1a2e;
  --bg-hero-end: #16213e;
  --bg-about: #0d0d15;
  --bg-projects: #0a0a12;
  --bg-contact: #080810;
  --text-primary: #ffffff;
  --text-body: rgba(255, 255, 255, 0.45);
  --text-muted: rgba(255, 255, 255, 0.15);
  --accent-gold: #e2b340;
  --accent-cyan: #4ecdc4;
  --accent-purple: #a78bfa;

  /* Typography */
  --font-stack: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-hero: clamp(3rem, 8vw, 6rem);
  --font-heading: clamp(1.5rem, 3vw, 2.5rem);
  --font-body: 1rem;
  --font-label: 0.75rem;
}
```

- [ ] **Step 2: Write base reset + body + scroll snap**

```css
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }

html {
  scroll-snap-type: y mandatory;
  scroll-behavior: smooth;
}

body {
  font-family: var(--font-stack);
  background: var(--bg-hero);
  color: var(--text-primary);
  overflow-x: hidden;
}

.section {
  min-height: 100vh;
  scroll-snap-align: start;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  padding: 80px 24px;
}
```

- [ ] **Step 3: Write section-specific background colors**

```css
#hero { background: linear-gradient(135deg, var(--bg-hero) 0%, var(--bg-hero-mid) 40%, var(--bg-hero-end) 100%); }
#about { background: var(--bg-about); }
#projects { background: var(--bg-projects); }
#contact { background: var(--bg-contact); }
```

- [ ] **Step 4: Preview in browser**

Open page — each section should fill the viewport with correct background colors. Scroll snap should work between sections.

- [ ] **Step 5: Commit**

```bash
git add landing-page/css/style.css
git commit -m "feat: CSS design tokens and base section layout with scroll snap"
```

---

### Task 3: Navigation Bar

**Files:**
- Modify: `landing-page/css/style.css`

- [ ] **Step 1: Write nav styles**

```css
nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  background: rgba(10, 10, 10, 0.8);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  transition: background 0.3s ease;
}

nav .logo {
  font-size: 0.875rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  color: var(--text-primary);
}

nav .nav-links {
  display: flex;
  gap: 24px;
  list-style: none;
}

nav .nav-links a {
  font-size: var(--font-label);
  color: rgba(255, 255, 255, 0.4);
  text-decoration: none;
  letter-spacing: 0.1em;
  transition: color 0.3s ease;
}

nav .nav-links a:hover {
  color: var(--text-primary);
}
```

- [ ] **Step 2: Preview — verify fixed nav with blur effect**

- [ ] **Step 3: Commit**

```bash
git add landing-page/css/style.css
git commit -m "feat: fixed navigation bar with glassmorphism"
```

---

### Task 4: Hero Section Styling

**Files:**
- Modify: `landing-page/css/style.css`

- [ ] **Step 1: Write hero typography styles**

```css
.hero-label {
  font-size: var(--font-label);
  color: rgba(255, 255, 255, 0.3);
  letter-spacing: 0.4em;
  margin-bottom: 16px;
}

.hero-title {
  font-size: var(--font-hero);
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1;
}

.hero-subtitle {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.4);
  letter-spacing: 0.25em;
  margin-top: 16px;
}

.hero-divider {
  width: 30px;
  height: 1px;
  background: rgba(255, 255, 255, 0.2);
  margin: 24px auto;
}
```

- [ ] **Step 2: Write geometric decoration styles + animation**

```css
.geo-ring {
  position: absolute;
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 50%;
  pointer-events: none;
}

.geo-ring:nth-child(1) { width: 400px; height: 400px; top: -150px; right: -100px; animation: drift 18s ease-in-out infinite; }
.geo-ring:nth-child(2) { width: 250px; height: 250px; bottom: -80px; left: -60px; animation: drift 15s ease-in-out infinite reverse; }
.geo-ring:nth-child(3) { width: 300px; height: 300px; top: 20%; left: -120px; animation: drift 20s ease-in-out infinite 3s; }

.geo-line {
  position: absolute;
  width: 1px;
  height: 100px;
  background: linear-gradient(to bottom, transparent, rgba(255, 255, 255, 0.06), transparent);
  pointer-events: none;
}

.geo-line:nth-child(1) { top: 10%; left: 30%; animation: drift-vertical 16s ease-in-out infinite; }
.geo-line:nth-child(2) { bottom: 15%; right: 25%; animation: drift-vertical 19s ease-in-out infinite reverse; }

@keyframes drift {
  0%, 100% { transform: translate(0, 0); }
  50% { transform: translate(15px, -20px); }
}

@keyframes drift-vertical {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-30px); }
}
```

- [ ] **Step 3: Write scroll indicator styles + bounce animation**

```css
.scroll-indicator {
  position: absolute;
  bottom: 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  animation: bounce 2s ease-in-out infinite;
}

.scroll-indicator .arrow {
  font-size: 1.25rem;
  color: rgba(255, 255, 255, 0.2);
}

.scroll-indicator .scroll-text {
  font-size: 0.625rem;
  color: rgba(255, 255, 255, 0.2);
  letter-spacing: 0.15em;
}

@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(8px); }
}
```

- [ ] **Step 4: Preview hero section**

Verify: large "JEFF" centered, decorative rings drifting, scroll indicator bouncing at bottom.

- [ ] **Step 5: Commit**

```bash
git add landing-page/css/style.css
git commit -m "feat: hero section styling with geometric decorations and animations"
```

---

### Task 5: About + Projects + Contact Sections

**Files:**
- Modify: `landing-page/css/style.css`

- [ ] **Step 1: Write section number + about styles**

```css
.section-number {
  font-size: var(--font-label);
  color: var(--text-muted);
  letter-spacing: 0.25em;
  position: absolute;
  top: 24px;
  left: 32px;
}

.about-content {
  max-width: 560px;
  text-align: center;
}

.about-content h2 {
  font-size: var(--font-heading);
  font-weight: 700;
  line-height: 1.4;
  margin-bottom: 16px;
}

.about-content p {
  font-size: var(--font-body);
  color: var(--text-body);
  line-height: 1.8;
}
```

- [ ] **Step 2: Write project card styles**

```css
.projects-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  max-width: 640px;
  margin-top: 16px;
}

.project-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 20px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.3s ease;
  text-decoration: none;
  color: inherit;
}

.project-card:hover {
  transform: translateY(-2px);
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
}

.project-card h3 {
  font-size: 1.125rem;
  font-weight: 700;
}

.project-card p {
  font-size: 0.875rem;
  color: var(--text-body);
  margin-top: 4px;
}

.project-card .arrow {
  font-size: 0.875rem;
  color: rgba(255, 255, 255, 0.2);
  transition: color 0.3s ease;
}

.project-card:hover .arrow {
  color: var(--text-body);
}

.project-card.gold h3 { color: var(--accent-gold); }
.project-card.cyan h3 { color: var(--accent-cyan); }
.project-card.purple h3 { color: var(--accent-purple); }
```

- [ ] **Step 3: Write contact section styles**

```css
.contact-content {
  text-align: center;
}

.contact-content h2 {
  font-size: var(--font-heading);
  font-weight: 700;
  margin-bottom: 20px;
}

.contact-links {
  display: flex;
  gap: 16px;
  justify-content: center;
}

.contact-links a {
  font-size: 0.875rem;
  color: rgba(255, 255, 255, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 8px 20px;
  border-radius: 24px;
  text-decoration: none;
  transition: all 0.3s ease;
}

.contact-links a:hover {
  color: var(--text-primary);
  border-color: rgba(255, 255, 255, 0.3);
}
```

- [ ] **Step 4: Preview all sections**

Verify: About centered text, Projects with 3 colored cards, Contact with capsule buttons. Hover effects work.

- [ ] **Step 5: Commit**

```bash
git add landing-page/css/style.css
git commit -m "feat: about, projects, and contact section styles"
```

---

### Task 6: Scroll Fade-In Animations (JavaScript)

**Files:**
- Modify: `landing-page/js/main.js`

- [ ] **Step 1: Write Intersection Observer for fade-in elements**

```javascript
document.addEventListener('DOMContentLoaded', () => {
  // Fade-in on scroll
  const fadeElements = document.querySelectorAll('.fade-in');

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
  );

  fadeElements.forEach((el) => observer.observe(el));
});
```

- [ ] **Step 2: Write fade-in CSS classes**

Add to `style.css`:

```css
.fade-in {
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.8s ease, transform 0.8s ease;
}

.fade-in.visible {
  opacity: 1;
  transform: translateY(0);
}

/* Stagger children */
.fade-in:nth-child(2) { transition-delay: 0.1s; }
.fade-in:nth-child(3) { transition-delay: 0.2s; }
.fade-in:nth-child(4) { transition-delay: 0.3s; }
```

- [ ] **Step 3: Preview — scroll through page**

Verify: elements fade in as they enter viewport. About text fades in, project cards stagger in, contact section fades in.

- [ ] **Step 4: Commit**

```bash
git add landing-page/js/main.js landing-page/css/style.css
git commit -m "feat: scroll-triggered fade-in animations with Intersection Observer"
```

---

### Task 7: Responsive Design

**Files:**
- Modify: `landing-page/css/style.css`

- [ ] **Step 1: Write tablet breakpoint (768-1024px)**

```css
@media (max-width: 1024px) {
  .section { padding: 60px 20px; }
  nav { padding: 12px 20px; }
}
```

- [ ] **Step 2: Write mobile breakpoint (<768px)**

```css
@media (max-width: 768px) {
  nav .nav-links { display: none; }
  .section { padding: 48px 16px; }
  .section-number { left: 16px; top: 16px; }
  .about-content { max-width: 100%; }
  .projects-grid { max-width: 100%; }
  .contact-links { flex-direction: column; align-items: center; }
}
```

- [ ] **Step 3: Test at mobile, tablet, desktop widths**

Resize browser. Verify: mobile hides nav links, spacing adjusts, contact links stack vertically. Font sizes scale via clamp().

- [ ] **Step 4: Commit**

```bash
git add landing-page/css/style.css
git commit -m "feat: responsive design for tablet and mobile"
```

---

### Task 8: Final Polish + Launch Config

**Files:**
- Modify: `landing-page/css/style.css` (minor tweaks if needed)
- Create: `.claude/launch.json` (dev server config)

- [ ] **Step 1: Add launch config for preview**

Create/update `.claude/launch.json` to include a simple HTTP server for the landing page:

```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "landing-page",
      "runtimeExecutable": "python3",
      "runtimeArgs": ["-m", "http.server", "3000", "--directory", "landing-page"],
      "port": 3000
    }
  ]
}
```

- [ ] **Step 2: Start preview server and verify**

Start the `landing-page` server via preview_start. Navigate through all sections. Check:
- Scroll snap works between sections
- Nav is fixed with blur
- Hero animations play (rings drift, indicator bounces)
- Fade-in triggers on scroll
- Project cards hover correctly
- Responsive at different widths

- [ ] **Step 3: Commit**

```bash
git add .claude/launch.json
git commit -m "feat: add dev server config for landing page preview"
```

- [ ] **Step 4: Update FPMS project status**

Mark Phase 1 (design) complete, update next_step to Phase 2 or note that development is done for v1.
