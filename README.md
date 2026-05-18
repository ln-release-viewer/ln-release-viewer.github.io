# 📚 Light Novel Release Viewer

A clean, responsive, visual dashboard designed to track upcoming English light novel releases **complete with their original publisher cover art**. 

This project operates as an independent, visual expansion of the curated textual schedules maintained by the open-source community, making it easy to see what is coming out at a glance.

🔗 **Live Demo:** [https://ln-release-viewer.github.io](https://ln-release-viewer.github.io)

---

## ✨ Features

- **Sticky Controls Header:** The search bar and theme controls remain pinned to the top of the viewport for seamless navigation while scrolling through massive multi-month calendars.
- **Pill Switch Toggle:** A custom, modern toggle switch for Fluid Light/Dark mode transitions that respects and preserves user browser preferences via local storage.
- **Lightning-Fast Live Filtering:** Instant client-side text filtering across titles, volume counts, and publisher tags.
- **Smart Empty States:** Gracefully alerts the user if a specific query returns no results instead of collapsing the page layout.
- **Keyboard Shortcut:** Press `/` anywhere on the page to instantly jump focus directly into the header search input field.
- **Automated Data Lifecycle:** A headless CI/CD browser pipeline that completely automates data synchronization without requiring manual developer builds.

---

## 🛠️ Data Pipeline & Automation

The site updates automatically via a scheduled **GitHub Actions** workflow. The automated backend handles compilation through a multi-stage Python and browser automation stack:

1. **Upstream Sync:** Clones the latest structured source text tables from the repository index.
2. **Parsing:** Parses markdown data tables directly into a unified schema (`scripts/parse_readme.py`).
3. **Metadata Enrichment:** Merges volume listings with comprehensive catalog identifiers (`scripts/add_isbns.py`).
4. **Headless Scraper:** Spins up a virtual frame buffer (`Xvfb`) and runs an automated browser instance via Playwright/Selenium to locate and save official covers into the local asset tree (`scripts/fetch_covers.py`).
5. **Static Build:** Astro compiles the final production build into optimized, static HTML, which is automatically pushed directly to GitHub Pages.

---

## 🚀 Project Structure

```text
/
├── data/
│   └── releases.json       # Clean, aggregated database of upcoming books
├── public/
│   ├── covers/             # Cached cover art images indexed by script pipeline
│   └── icons/              # SVG vectors for UI components
├── scripts/
│   ├── parse_readme.py     # Extracts text listings from upstream source
│   ├── add_isbns.py        # Enriches volume objects with catalog criteria
│   └── fetch_covers.py     # Headless Playwright browser fetching utility
├── src/
│   ├── layouts/
│   │   └── Layout.astro    # Core document shell, dark mode classes, and global layout styles
│   └── pages/
│       └── index.astro     # Main application dashboard view & client filtering logic
├── package.json
└── astro.config.mjs

