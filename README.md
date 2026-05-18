# 📚 Light Novel Release Viewer

A clean, fast, static Astro-powered website that aggregates and displays upcoming English light novel releases.  
This project automatically fetches release data weekly, parses it into structured JSON, and renders it in a searchable, mobile-friendly grid with dark mode support.

This is a personal, open-source hobby project — built for convenience and discoverability.

---

## ✨ Features

- **Automatic weekly updates** via GitHub Actions  
- **Chronological grouping** (Month → Releases)  
- **Responsive grid layout**  
- **Instant search filtering**  
- **Dark / Light mode toggle**  
- **Fallback cover images**  
- **Publisher, volume, and date metadata**  
- **Direct links to official publisher pages**  
- **Fully static — no backend required**

---

## 🛠️ Tech Stack

- **Astro** (static site generation)
- **Vanilla JS** for client-side filtering
- **GitHub Actions** for scheduled data updates
- **Cheerio** for parsing LNRelease HTML
- **CSS variables** for theme support

---

## 🚀 Development

Clone the repo:

```bash
git clone https://github.com/<your-username>/ln-release-viewer.git
cd ln-release-viewer
```
Install dependencies:
```bash
npm install
```
Run locally:
```bash
npm run dev
```
Build for production:
```bash
npm run build
```
Preview the build:
```bash
npm run preview
```

## 🔄 Automated Data Updates

A GitHub Action runs weekly to:

    1. Fetch the latest LNRelease data

    2. Parse the release table

    3. Generate data/releases.json

    4. Commit changes

    5. Trigger a rebuild of the GitHub Pages site

This keeps the site up-to-date with zero manual maintenance.

## 📁 Project Structure

```
/
├── public/              # Static assets (icons, placeholder covers)
├── src/
│   ├── components/      # Reusable UI components
│   ├── layouts/         # Layout wrappers
│   ├── pages/           # Astro pages
│   └── scripts/         # Parsing + utilities
├── data/
│   └── releases.json    # Auto-generated release data
└── .github/workflows/   # Scheduled update pipeline
```

## ⚠️ Disclaimer

This repository is an unofficial, independent, open‑source hobby project.
It is not affiliated with, endorsed by, or partnered with the LNRelease project, its maintainers, or any official light novel publishers.

All book covers, illustrations, logos, and promotional assets are the exclusive intellectual property of their respective artists, creators, and licensing publishers.

Images are surfaced strictly for descriptive, identification, and cataloging purposes under fair use.
Each card links directly to the official publisher’s webpage to support discoverability and direct traffic to primary storefronts.

If you are a rights holder and would like an asset removed or credited differently, please open an issue.

## 📄 License

This project is licensed under the MIT License.  
See the [LICENSE](./LICENSE) file for details.