# DJ Guide Event Scraper & Lead Generator

A powerful automation tool that scrapes event data from the Dutch DJ guide website (**djguide.nl**), extracts contact emails from event websites, and organizes everything into Google Sheets for direct outreach and lead generation.

---

## Overview

This script acts as a **lead generation engine** for event promoters, venue owners, DJ agencies, and marketing professionals. It automatically:

- Collects upcoming events (name, date, links) from `djguide.nl`
- Extracts email addresses from each event’s website (main page, contact, about, events, tickets pages)
- Avoids detection using rotating proxies and undetectable Chrome drivers
- Uploads the collected data to **Google Sheets** and **GitHub** for team sharing and version control
- Highlights duplicate email entries to prevent redundant outreach

**The result:** a clean, continuously updated list of event organisers, venues, and DJs with direct contact emails—ready for your marketing or sponsorship campaigns.

---

## Features

- **Undetectable scraping** – Uses `undetected-chromedriver` and custom user‑agent to bypass bot protection.
- **Proxy rotation** – Fetches free HTTPS proxies, tests them, and removes blocked ones automatically.
- **Smart email extraction** – Scans main pages plus common sub‑paths (`/contact`, `/about`, `/events`, `/tickets`) and validates email formats.
- **Resume capability** – Already scraped events are skipped, and email records are stored locally to avoid duplicates.
- **Google Sheets integration** – Uploads all new email entries to a shared spreadsheet, with duplicate highlighting.
- **GitHub sync** – Automatically pushes all local CSV files to a GitHub repository for backup and collaboration.
- **Headless mode** – Runs in the background without opening a visible browser window.

---

## How It Works

### Phase 0 – Proxy Fetching
- Retrieves a list of HTTPS proxies from `free-proxy-list.net`
- Tests each proxy against `httpbin.org/ip`
- Saves working proxies to `proxies.txt`

### Phase 1 – Event Scraping
- Loads a proxy and launches an undetectable Chrome instance
- Navigates to `djguide.nl/events.p`
- Closes pop‑ups and checks for login/block pages
- Clicks each event card to open the detail page
- Extracts event name, date, and filtered external links (excluding social media and the domain itself)
- Saves complete entries to `events.csv`

### Phase 2 – Email Extraction
- Reads `events.csv` to get the website links per event
- For each link, sends a request (using `requests` or Selenium if needed) and extracts all valid email addresses
- Saves unique emails to `events_email.csv` along with the event name, date, and source website

### Phase 3 – Google Sheets Upload
- Reads `events_email.csv` and compares with a local record of already uploaded rows (`uploaded_data.csv`)
- Appends only new rows to the Google Sheet (using service account credentials)
- Highlights duplicate rows (based on event name, date, website, and email) with a red background

### Additional Sync – GitHub Upload
- Every iteration, all files in the script directory are uploaded/updated to your GitHub repository (requires token and repo name)

---

## Impact – Why This Matters

### 🚀 Lead Generation at Scale
- No more manual browsing and copy‑pasting. The script automatically builds a targeted list of event organisers and venues in the Netherlands.
- Each row includes a verified email address, enabling **direct, personalised email outreach**.

### 📈 Boost Marketing & Sponsorship ROI
- Event promoters can reach out to DJs, artists, or brands.
- Venue owners can connect with event organisers for collaborations.
- DJ agencies can identify new booking opportunities.

### 💡 Time Savings
- What used to take hours of research per week now runs automatically, 24/7, with scheduled execution.
- The script handles proxy rotation and bot‑detection so you don’t have to.

### 🧹 Data Quality
- Duplicate detection and validation ensure you don’t waste time contacting the same person twice.
- All data is stored in structured CSV and synchronised to a central Google Sheet for easy analysis and team access.

---

## Setup & Installation

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/djguide-scraper.git
cd djguide-scraper
