# Scraper Service

A production-grade, modular scraping platform built on FastAPI.

## 🎯 What Is This?

**From:** Facebook post scraper  
**To:** Universal web crawling platform

Two capabilities in one service:

- **🌐 Recursive Web Crawler** — Full-site crawling with queue-based URL discovery, depth control, domain filtering, robots.txt compliance, and 20+ content type support (HTML, PDF, images, videos, Office docs)
- **📱 Facebook Scraper** — Scrape posts, reels, page metadata from any Facebook page using Selenium; background jobs with real-time progress polling; Excel export with embedded images

---

## ✨ Key Features

### Recursive Crawler
✅ Queue-based URL scheduling with priority  
✅ URL deduplication & normalization  
✅ Depth-limited crawling  
✅ Domain whitelisting/blacklisting  
✅ robots.txt compliance  
✅ Content-type detection (20+ types)  
✅ Background jobs with progress tracking  
✅ Real-time statistics  

### Content Processing
✅ PDF text extraction with OCR fallback  
✅ Image metadata + OCR  
✅ HTML metadata extraction  
✅ Link discovery  
✅ Video URL extraction  

### Production Features
✅ Thread-safe operations  
✅ Graceful error handling  
✅ Consistent API responses  
✅ Performance metrics  
✅ Job management (50 concurrent jobs)  

---

## Quick Start

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt --only-binary=:all:
venv/bin/playwright install chromium

cp .env.example .env

cd app
PYTHONPATH=.. ../venv/bin/uvicorn main:app --reload --port 8000
```

API → `http://localhost:8000`  
Swagger → `http://localhost:8000/docs`

---

## Test it immediately (no login needed)

```bash
# Crawl any URL — full pipeline
curl "http://localhost:8000/crawl/test?url=https://www.nasa.gov/"

# Check all platforms
curl http://localhost:8000/platforms

# DB stats
curl http://localhost:8000/db/stats
```

---

## 📖 Documentation

| File | Contents |
|------|----------|
| [FEATURES.md](./FEATURES.md) | Every feature with descriptions |
| [PRODUCTION_ROADMAP.md](./PRODUCTION_ROADMAP.md) | Current vs target state, milestones, architecture scoring |
| [TEST_GUIDE.md](./TEST_GUIDE.md) | 12 test cases, benchmarks, validation checklist |
| [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) | What was built, stats, architecture flow |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System design, pipeline, module map, DB schema |
| [SETUP.md](./SETUP.md) | Installation, login options, troubleshooting |

---

## Requirements

- Python 3.11+
- Node.js 18+ (optional, not required currently)
- Google Chrome / Chromium
- ffmpeg (optional, for reel DASH audio merge)
