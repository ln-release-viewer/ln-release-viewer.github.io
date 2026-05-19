# 📚 Light Novel Release Viewer

An Astro-powered website that aggregates and displays upcoming English light novel releases.  
This project automatically fetches release data weekly from [lnrelease.github.io](https://github.com/LNRelease/lnrelease.github.io), parses it into structured JSON, and renders it in a searchable grid of novels with their corresponding covers.

This is a personal, open-source hobby project — built for convenience and discoverability of upcoming light novels.

---

## ✨ Features

- **Automatic weekly updates** via GitHub Actions  
- **Chronological grouping** (Month → Releases)
- **Search filtering**  
- **Dark / Light mode toggle** 
- **Publisher, volume, and date metadata**  
- **Direct links to official publisher pages**

---

## 🛠️ Tech Stack

- **Astro** for static site generation
- **Vanilla JS** for client-side filtering
- **GitHub Actions** for scheduled data updates
- **Python** for parsing LNRelease data and fetching covers
- **CSS variables** for theme support

---

## 🚀 Development

Clone the repo:

```bash
git clone https://github.com/ln-release-viewer/ln-release-viewer.github.io.git
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

    2. Parse the README and generate data/releases.json

    3. Fetch covers

    4. Commit changes

    5. Trigger a rebuild of the GitHub Pages site

This keeps the site up-to-date.

## 📁 Project Structure

```
/
├── .github/
│   └── workflows/
│       ├── deploy.yml              # Builds + deploys Astro site to GitHub Pages
│       └── update-releases.yml     # Weekly LNRelease data update pipeline
│
├── data/
│   └── releases.json               # Auto-generated release data (parsed weekly)
│
├── public/
│   ├── covers/                     # Auto-fetched cover images
│   ├── icons/                      # Page icons
│   ├── favicon.ico                 # Site favicon (ICO)
│   └── favicon.svg                 # Site favicon (SVG)
│
├── scripts/
│   ├── scrapers/                   # Individual publisher scrapers
│   ├── add_isbns.py                # Adds ISBNs to releases for Open Library / Google Books
│   ├── fetch_covers.py             # Fetches cover images from linked publishers and APIs
│   ├── parse_readme.py             # Parses LNRelease README into structured JSON
│   └── scrape_covers.py            # Helper for scraper calls
│
├── src/
│   ├── layouts/
│   │   └── Layout.astro            # Global layout wrapper
│   └── pages/
│       └── index.astro             # Main release viewer page
│
├── LICENSE                         # MIT License
└── package.json                    # Dependencies + scripts

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