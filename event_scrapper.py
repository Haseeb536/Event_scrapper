import sys
import subprocess

# -------------------- PHASE -1: AUTO-INSTALL DEPENDENCIES --------------------
required_packages = [
    "requests",
    "lxml",
    "beautifulsoup4",
    "undetected-chromedriver",
    "selenium",
    "gspread",
    "google-auth"
]
for package in required_packages:
    try:
        __import__(package.replace("-", "_"))
    except ImportError:
        print(f"📦 Installing missing package: {package}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# -------------------- IMPORTS --------------------
import os
import re
import time
import csv
from datetime import datetime
from urllib.parse import urlparse, urljoin
from itertools import cycle
from lxml.html import fromstring
import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import gspread
from google.oauth2.service_account import Credentials

# Avoid WinError 6 spam on quit
uc.Chrome.__del__ = lambda self: None

# -------------------- CONSTANTS --------------------
URL = "https://www.djguide.nl/events.p"
LOGIN_BLOCK_URL = "https://www.djguide.nl/pagecontent.p?pagename=ip_login"
BASE_DOMAIN = "djguide.nl"
EMAIL_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
CUSTOM_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/116.0.5845.97 Safari/537.36"
)

# -------------------- FILE PATHS --------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROXY_FILE = os.path.join(SCRIPT_DIR, "proxies.txt")
EVENTS_CSV = os.path.join(SCRIPT_DIR, "events.csv")
EMAILS_CSV = os.path.join(SCRIPT_DIR, "events_email.csv")
UPLOADED_DATA_CSV = os.path.join(SCRIPT_DIR, "uploaded_data.csv")

# Google Sheets config (Phase 4)
SHEET_TOKEN = "13fEOnuQKBTMPkhwr-OmI84kbsDq-jup_mnv9CcOxhlo"
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "credentials.json")

# -------------------- PHASE 5: GIT SYNC HELPERS --------------------
def _git_run(args, cwd=SCRIPT_DIR, quiet=False):
    try:
        if quiet:
            subprocess.run(args, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        else:
            subprocess.run(args, cwd=cwd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        if not quiet:
            print(f"⚠️ git command failed: {' '.join(args)} -> {e}")
        return False

def ensure_git_repo():
    """Ensure this folder has the full GitHub repo cloned, with correct config."""
    token = "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" 
    repo = os.getenv("GITHUB_REPO", "Haseeb536/Event_scrapper")  # owner/repo

    if not token or not repo:
        print("⚠️ GITHUB_TOKEN or GITHUB_REPO not set.")
        return False

    remote_url = f"https://{token}@github.com/{repo}.git"

    # If no .git folder, clone the repo fresh
    if not os.path.isdir(os.path.join(SCRIPT_DIR, ".git")):
        print("📥 Cloning full repo from GitHub...")
        _git_run(["git", "clone", remote_url, "."], cwd=SCRIPT_DIR)

    # Configure Git user
    git_user = os.getenv("GIT_USER_NAME", "Haseeb536")
    git_email = os.getenv("GIT_USER_EMAIL", "haseeebramzan536@gmail.com")
    _git_run(["git", "config", "user.name", git_user], quiet=True)
    _git_run(["git", "config", "user.email", git_email], quiet=True)

    # Ensure remote URL is set correctly
    _git_run(["git", "remote", "set-url", "origin", remote_url], quiet=True)

    return True

def git_sync(files_to_commit, message):
    """Pull latest, add changes, commit, and push safely."""
    if not ensure_git_repo():
        return False

    branch = os.getenv("GIT_BRANCH", "main")

    # Checkout branch
    _git_run(["git", "checkout", branch], quiet=True)

    # Pull latest changes to avoid overwriting remote
    _git_run(["git", "pull", "--rebase", "origin", branch], quiet=True)

    # Stage specified files
    if not _git_run(["git", "add"] + files_to_commit):
        return False

    # Commit changes
    _git_run(["git", "commit", "-m", message, "--allow-empty"], quiet=True)

    # Push without force
    if _git_run(["git", "push", "-u", "origin", branch]):
        print(f"⬆️ Git pushed successfully: {message}")
        return True
    else:
        print("❌ Git push failed.")
        return False

# -------------------- PHASE 0: FETCH & TEST PROXIES --------------------
def get_proxies():
    url = 'https://free-proxy-list.net/'
    response = requests.get(url, timeout=15)
    parser = fromstring(response.text)
    proxies = set()
    for i in parser.xpath('//tbody/tr'):
        # HTTPS only
        if i.xpath('.//td[7][contains(text(),"yes")]'):
            ip = i.xpath('.//td[1]/text()')
            port = i.xpath('.//td[2]/text()')
            if ip and port:
                proxies.add(f"{ip[0]}:{port[0]}")
    return proxies

def fetch_and_test_proxies():
    print("🌐 Fetching proxies...")
    proxies = get_proxies()
    proxy_pool = cycle(proxies)
    test_url = 'https://httpbin.org/ip'
    working = []

    for i in range(1, len(proxies) + 1):
        proxy = next(proxy_pool)
        print(f"Request #{i} Testing {proxy}")
        try:
            resp = requests.get(test_url, proxies={"http": proxy, "https": proxy}, timeout=5)
            print("✅ Working:", resp.json())
            working.append(proxy)
            with open(PROXY_FILE, 'a', encoding='utf-8') as f:
                f.write(proxy + "\n")
        except Exception:
            print("❌ Skipping. Connection error")
        time.sleep(0.4)

    if working:
        git_sync([PROXY_FILE], "Update proxies.txt (fetched & tested)")
    else:
        print("⚠ No working proxies found! Script will run without proxy.")

# -------------------- UTILS --------------------
def load_proxies():
    if not os.path.exists(PROXY_FILE):
        return []
    with open(PROXY_FILE, "r") as f:
        return [p.strip() for p in f if p.strip()]

def save_proxies(proxies):
    with open(PROXY_FILE, "w") as f:
        for p in proxies:
            f.write(p + "\n")
    git_sync([PROXY_FILE], "Rotate proxies.txt (remove blocked)")

def init_driver(proxy=None, headless=False):
    options = uc.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--incognito")
    options.add_argument(f"user-agent={CUSTOM_UA}")
    if headless:
        options.add_argument("--headless=new")
    if proxy:
        options.add_argument(f"--proxy-server={proxy}")
    driver = uc.Chrome(options=options)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """
    })
    return driver

def clean_field(val):
    return str(val).strip().replace("\u00A0", "").strip() if val else ""

def all_fields_filled(row):
    return all([
        clean_field(row.get("Event Name")),
        clean_field(row.get("Event Date")),
        clean_field(row.get("Links"))
    ])

# -------------------- CSV INIT --------------------
if not os.path.exists(EVENTS_CSV):
    with open(EVENTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Event Name", "Event Date", "Links", "Event URL"])
    git_sync([EVENTS_CSV], "Initialize events.csv")

if not os.path.exists(EMAILS_CSV):
    with open(EMAILS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # 7 columns (as requested): Event name, Event date, Website link, Email Address, Email sent on, Email already sent before on, Instructions
        writer.writerow(["Event Name", "Event Date", "Website link", "Email Address", "Email sent on", "Email already sent before on", "Instructions"])
    git_sync([EMAILS_CSV], "Initialize events_email.csv")

if not os.path.exists(UPLOADED_DATA_CSV):
    with open(UPLOADED_DATA_CSV, "w", newline="", encoding="utf-8") as f:
        pass
    git_sync([UPLOADED_DATA_CSV], "Initialize uploaded_data.csv")

# -------------------- PHASE 1: SCRAPE EVENTS (exact same shape) --------------------
def load_existing_events():
    events = {}
    if os.path.exists(EVENTS_CSV):
        with open(EVENTS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                events[row["Event URL"]] = row
    return events

def close_popups(driver):
    try:
        popups = driver.find_elements(By.CSS_SELECTOR, "button.close, .modal-close, .popup-close")
        for popup in popups:
            if popup.is_displayed():
                popup.click()
                print("🛑 Closed a popup")
                time.sleep(0.5)
        popups = driver.find_elements(By.XPATH, '//*[@id="dismiss-button"]')
        for popup in popups:
            if popup.is_displayed():
                popup.click()
                print("🛑 Closed a popup")
                time.sleep(0.5)
        time.sleep(1)
    except Exception:
        pass

def get_filtered_links(driver):
    """Extract and filter actual href links from possible link sections."""
    link_paths = [
        '//*[@id="partydetail"]/div[4]/div[1]/div[2]',
        '//*[@id="partydetail"]/div[4]/div[2]/div[2]',
        '//*[@id="partydetail"]/div[4]/div[3]/div[2]',
        '//*[@id="partydetail"]/div[4]/div[4]/div[2]',
        '//*[@id="partydetail"]/div[4]/div[5]/div[2]',
        '//*[@id="partydetail"]/div[4]/div[6]/div[2]',
        '//*[@id="partydetail"]/div[4]/div[7]/div[2]'
    ]
    links = set()
    for path in link_paths:
        try:
            link_container = driver.find_element(By.XPATH, path)
            anchors = link_container.find_elements(By.TAG_NAME, "a")
            for a in anchors:
                href = a.get_attribute("href")
                if not href:
                    continue
                domain = urlparse(href).netloc.lower()
                if "facebook.com" in domain or "instagram.com" in domain or "google.com" in domain or BASE_DOMAIN in domain:
                    continue
                links.add(href.strip())
        except Exception:
            continue
    return " | ".join(sorted(links))

def scrape_with_proxy(proxy, proxies_list):
    existing_events = load_existing_events()
    print(f"🔌 Trying proxy: {proxy or 'DIRECT'}")
    driver = init_driver(proxy)
    wait = WebDriverWait(driver, 20)

    try:
        driver.get(URL)
        time.sleep(2)
        close_popups(driver)

        # Check for forbidden access
        if "403 - Forbidden" in driver.page_source or "Access is denied" in driver.page_source:
            print(f"🚫 Proxy {proxy} blocked with 403 Forbidden. Removing proxy.")
            driver.quit()
            try:
                proxies_list.remove(proxy)
            except ValueError:
                pass
            save_proxies(proxies_list)
            return False

        if LOGIN_BLOCK_URL in driver.current_url or "Inloggen is nodig" in driver.page_source:
            print(f"🚫 Proxy {proxy} blocked (login wall). Removing proxy.")
            driver.quit()
            try:
                proxies_list.remove(proxy)
            except ValueError:
                pass
            save_proxies(proxies_list)
            return False

        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "#containerupdpartyagenda_main > div:nth-child(2) > div.list-group")
        ))
        print("✅ Container loaded!")

        event_cards = driver.find_elements(By.CSS_SELECTOR, "a.list-group-item.agendaitem")
        total_events = len(event_cards)

        for idx in range(total_events):
            try:
                event_cards = driver.find_elements(By.CSS_SELECTOR, "a.list-group-item.agendaitem")
                if idx >= len(event_cards):
                    print(f"⚠️ Event index {idx} out of range, skipping...")
                    continue

                event_url = event_cards[idx].get_attribute("href")

                if event_url in existing_events and all_fields_filled(existing_events[event_url]):
                    print(f"⏩ Skipping fully scraped: {event_url}")
                    continue

                print(f"📌 Clicking event {idx+1}/{total_events}: {event_url}")

                driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", event_cards[idx]
                )
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", event_cards[idx])
                time.sleep(1)
                close_popups(driver)

                if LOGIN_BLOCK_URL in driver.current_url or "Inloggen is nodig" in driver.page_source:
                    print(f"🚫 Proxy {proxy} blocked mid-run. Removing proxy.")
                    driver.quit()
                    try:
                        proxies_list.remove(proxy)
                    except ValueError:
                        pass
                    save_proxies(proxies_list)
                    return False

                try:
                    name_elem = wait.until(EC.presence_of_element_located(
                        (By.XPATH, '//*[@id="eventinfo"]/div/div[1]/h2/div/div[3]/span[1]')
                    ))
                    name = clean_field(name_elem.text)
                except Exception:
                    name = ""

                try:
                    date_elem = driver.find_element(By.XPATH, '//*[@id="partydetail"]/div[3]/div[1]/div[2]/div/a')
                    date = clean_field(date_elem.text)
                except Exception:
                    date = ""

                links_text = get_filtered_links(driver)

                if all([name, date, links_text]):
                    existing_events[event_url] = {
                        "Event Name": name,
                        "Event Date": date,
                        "Links": links_text,
                        "Event URL": event_url
                    }
                    # Rewrite events.csv with current dict (as your original flow)
                    with open(EVENTS_CSV, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=["Event Name", "Event Date", "Links", "Event URL"])
                        writer.writeheader()
                        writer.writerows(existing_events.values())
                    print(f"✅ Saved: {name}")
                    git_sync([EVENTS_CSV], f"Update events.csv ({name})")
                else:
                    print(f"⚠️ Skipping incomplete event: {event_url}")

                driver.back()
                close_popups(driver)
                wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "#containerupdpartyagenda_main > div:nth-child(2) > div.list-group")
                ))
                time.sleep(1)

            except Exception as e:
                print(f"⚠️ Error scraping event {idx+1}: {e}")
                try:
                    driver.back()
                    close_popups(driver)
                except Exception:
                    pass

        driver.quit()
        return True

    except Exception as e:
        print(f"❌ Proxy failed: {proxy}, Error: {e}")
        driver.quit()
        return False

# -------------------- PHASE 2: EMAIL SCRAPING --------------------
def email_already_saved(name, date):
    if not os.path.exists(EMAILS_CSV):
        return False
    with open(EMAILS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Event Name"] == name and row["Event Date"] == date:
                return True
    return False

def save_email_row(row):
    with open(EMAILS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)
    git_sync([EMAILS_CSV], f"Append events_email.csv ({row[0]} - {row[1]})")

def fetch_emails_bs(url):
    emails = set()
    try:
        print(f"\n🔍 Checking: {url}")
        resp = requests.get(url, timeout=12, headers={"User-Agent": CUSTOM_UA})
        if resp.status_code != 200:
            return emails
        found = re.findall(EMAIL_REGEX, resp.text)
        # filter obvious junk like image @ 2x etc by requiring a dot TLD-ish part
        emails.update(e.lower() for e in found)
        if emails:
            print(f"📧 Emails found (requests) -> {len(emails)}")
    except Exception:
        pass
    return emails

def fetch_emails_uc(url):
    emails = set()
    try:
        driver = init_driver(headless=True)
        driver.get(url)
        time.sleep(3)
        found = re.findall(EMAIL_REGEX, driver.page_source)
        emails.update(e.lower() for e in found)
        driver.quit()
        if emails:
            print(f"📧 Emails found (headless UC) -> {len(emails)}")
    except Exception:
        pass
    return emails

def extract_emails_from_links():
    # Only run after Phase 1 has fully saved events.csv
    with open(EVENTS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["Event Name"]
            date = row["Event Date"]
            if email_already_saved(name, date):
                continue
            websites = row["Links"].split(" | ")
            for site in websites:
                site = site.strip()
                if not site:
                    continue
                emails = fetch_emails_bs(site)
                if not emails:
                    for sub in ["/contact", "/info", "/about", "/events", "/tickets"]:
                        emails.update(fetch_emails_bs(urljoin(site, sub)))
                if not emails:
                    for sub in [site] + [urljoin(site, s) for s in ["/contact", "/info", "/about", "/events", "/tickets"]]:
                        emails.update(fetch_emails_uc(sub))
                for email in emails:
                    save_email_row([
                        name, date, site, email, "", "", ""
                    ])

# -------------------- PHASE 4: UPLOAD TO GOOGLE SHEETS --------------------
def load_uploaded_data():
    uploaded = set()
    if not os.path.exists(UPLOADED_DATA_CSV):
        return uploaded
    with open(UPLOADED_DATA_CSV, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                uploaded.add(tuple(row))
    return uploaded

def append_to_uploaded_data(rows):
    with open(UPLOADED_DATA_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)
    git_sync([UPLOADED_DATA_CSV], f"Append uploaded_data.csv ({len(rows)} rows)")

def connect_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_TOKEN).sheet1
    return sheet

def upload_new_data():
    uploaded_set = load_uploaded_data()
    new_rows = []

    with open(EMAILS_CSV, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if not row:
                continue
            row_tuple = tuple(row)
            if row_tuple not in uploaded_set:
                new_rows.append(row_tuple)

    if not new_rows:
        print("✅ No new rows to upload.")
        return

    print(f"📤 Uploading {len(new_rows)} new rows to Google Sheet...")
    sheet = connect_google_sheet()
    # Append rows one by one (simplest/robust)
    for row in new_rows:
        sheet.append_row(list(row))
        print(f"✅ Uploaded: {row[0]} ({row[1]})")
        time.sleep(2)

    append_to_uploaded_data(new_rows)
    print("💾 Uploaded rows saved to uploaded_data.csv")

# -------------------- MAIN LOOP --------------------
if __name__ == "__main__":
    while True:
        # # Phase 0: proxies
        # fetch_and_test_proxies()
        # proxies = load_proxies()

        # # Phase 1: scrape events with proxy rotation
        # while True:
        #     if not proxies:
        #         print("🚫 No proxies left for Phase 1.")
        #         break
        #     current_proxy = proxies[0]
        #     success = scrape_with_proxy(current_proxy, proxies)
        #     if success:
        #         print("🎯 Events scraped successfully.")
        #         break
        #     else:
        #         print(f"🔄 Switching proxy (removing {current_proxy})...")
        #         try:
        #             proxies.remove(current_proxy)
        #         except ValueError:
        #             pass
        #         save_proxies(proxies)

        # # Phase 2: extract emails
        # extract_emails_from_links()

        # Phase 3: upload to Google Sheets
        try:
            upload_new_data()
        except Exception as e:
            print(f"⚠️ Google Sheets upload failed: {e}")

        if not proxies:
            print("🚫 No proxies left.")

        print("⏳ Sleeping for 2 hours...")
        time.sleep(7200)  # 2 hours
