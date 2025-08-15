import sys
import subprocess

# List of required packages
required_packages = [
    "requests",
    "lxml",
    "beautifulsoup4",
    "undetected-chromedriver",
    "selenium",
    "gspread",
    "google-auth",
    "PyGithub"
]

# Install missing packages
for package in required_packages:
    try:
        __import__(package.replace("-", "_"))
    except ImportError:
        print(f"📦 Installing missing package: {package}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Now import after ensuring installation
import os
import re
import time
import csv
import requests
from datetime import datetime
from urllib.parse import urlparse, urljoin
from itertools import cycle
from lxml.html import fromstring
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import gspread
from google.oauth2.service_account import Credentials
from github import Github

def upload_to_github():
    """
    Upload all files in the script directory to the GitHub repo.
    """
    g = Github("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")
    repo_name = os.getenv("GITHUB_REPO", "Haseeb536/Event_scrapper")
    repo = g.get_repo(repo_name)

    for file_name in os.listdir(SCRIPT_DIR):
        file_path = os.path.join(SCRIPT_DIR, file_name)
        if os.path.isfile(file_path):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            try:
                # Check if file already exists in repo
                contents = repo.get_contents(file_name)
                repo.update_file(
                    path=contents.path,
                    message=f"Update {file_name}",
                    content=content,
                    sha=contents.sha
                )
                print(f"🔄 Updated {file_name} on GitHub")
            except:
                # File does not exist, create it
                repo.create_file(
                    path=file_name,
                    message=f"Add {file_name}",
                    content=content
                )
                print(f"✅ Uploaded {file_name} to GitHub")

# Avoid WinError 6 spam
uc.Chrome.__del__ = lambda self: None

# -------------------- CONSTANTS --------------------
URL = "https://www.djguide.nl/events.p"
LOGIN_BLOCK_URL = "https://www.djguide.nl/pagecontent.p?pagename=ip_login"
BASE_DOMAIN = "djguide.nl"
CUSTOM_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.97 Safari/537.36"

# -------------------- FILE PATHS --------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROXY_FILE = os.path.join(SCRIPT_DIR, "proxies.txt")
EVENTS_CSV = os.path.join(SCRIPT_DIR, "events.csv")
EMAILS_CSV = os.path.join(SCRIPT_DIR, "events_email.csv")

# -------------------- PHASE 0: FETCH & TEST PROXIES --------------------
def get_proxies():
    url = 'https://free-proxy-list.net/'
    response = requests.get(url)
    parser = fromstring(response.text)
    proxies = set()
    for i in parser.xpath('//tbody/tr'):
        if i.xpath('.//td[7][contains(text(),"yes")]'):  # Only HTTPS
            proxy = ":".join([i.xpath('.//td[1]/text()')[0], i.xpath('.//td[2]/text()')[0]])
            proxies.add(proxy)
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
        except:
            print("❌ Skipping. Connection error")
        time.sleep(0.5)

    if not working:
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


# -------------------- CSV INIT --------------------
if not os.path.exists(EVENTS_CSV):
    with open(EVENTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Event Name", "Event Date", "Links", "Event URL"])


# -------------------- PHASE 1: SCRAPE EVENTS --------------------
# Constants
URL = "https://www.djguide.nl/events.p"
LOGIN_BLOCK_URL = "https://www.djguide.nl/pagecontent.p?pagename=ip_login"
BASE_DOMAIN = "djguide.nl"

# Directories
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROXY_FILE = os.path.join(SCRIPT_DIR, "proxies.txt")
CSV_FILE = os.path.join(SCRIPT_DIR, "events.csv")


# Ensure CSV exists with header
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Event Name", "Event Date", "Links", "Event URL"])

# Load existing events
def load_existing_events():
    events = {}
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                events[row["Event URL"]] = row
    return events

# Clean fields
def clean_field(val):
    return str(val).strip().replace("\u00A0", "").strip() if val else ""

def all_fields_filled(row):
    return all([clean_field(row.get("Event Name")),
                clean_field(row.get("Event Date")),
                clean_field(row.get("Links"))])

# Handle pop-ups
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
    except:
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
                if "facebook.com" in domain or "instagram.com" in domain or"google.com" in domain or BASE_DOMAIN in domain:
                    continue
                links.add(href.strip())
        except:
            continue
    return " | ".join(sorted(links))

def scrape_with_proxy(proxy):
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
            proxies.remove(proxy)
            save_proxies(proxies)
            return False

        if LOGIN_BLOCK_URL in driver.current_url or "Inloggen is nodig" in driver.page_source:
            print(f"🚫 Proxy {proxy} blocked (login wall). Removing proxy.")
            driver.quit()
            proxies.remove(proxy)
            save_proxies(proxies)
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

                # if event_url in existing_events and all_fields_filled(existing_events[event_url]):
                #     print(f"⏩ Skipping fully scraped: {event_url}")
                #     continue

                print(f"📌 Clicking event {idx+1}/{total_events}: {event_url}")

                # Scroll and JS click to avoid interception
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
                    return False

                try:
                    name_elem = wait.until(
                        EC.presence_of_element_located(
                            (By.XPATH, '//*[@id="eventinfo"]/div/div[1]/h2/div/div[3]/span[1]')
                        )
                    )
                    name = clean_field(name_elem.text)
                except:
                    name = ""

                try:
                    date_elem = driver.find_element(By.XPATH, '//*[@id="partydetail"]/div[3]/div[1]/div[2]/div/a')
                    date = clean_field(date_elem.text)
                except:
                    date = ""

                links_text = get_filtered_links(driver)

                if all([name, date, links_text]):
                    existing_events[event_url] = {
                        "Event Name": name,
                        "Event Date": date,
                        "Links": links_text,
                        "Event URL": event_url
                    }
                    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=["Event Name", "Event Date", "Links", "Event URL"])
                        writer.writeheader()
                        writer.writerows(existing_events.values())
                    print(f"✅ Saved: {name}")
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
                except:
                    pass

        driver.quit()
        return True

    except Exception as e:
        print(f"❌ Proxy failed: {proxy}, Error: {e}")
        driver.quit()
        return False

# -------------------- PHASE 2: EMAIL SCRAPING --------------------
EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"  # keep your regex
def ensure_email_csv():
    """Create the CSV with headers if it does not exist."""
    if not os.path.exists(EMAILS_CSV):
        with open(EMAILS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Event Name", "Event Date", "Website link", "Email Address",
                "Email sent on", "Email already sent before on", "Instructions"
            ])

def email_already_saved(name, date):
    ensure_email_csv()  # ensure file exists
    with open(EMAILS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Event Name", "").strip() == name and row.get("Event Date", "").strip() == date:
                return True
    return False

def save_email_row(row):
    ensure_email_csv()  # ensure file exists
    with open(EMAILS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)

def is_valid_email(email):
    email = email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        return False
    if not email[-1].isalnum():
        return False
    if re.match(r"^[0-9a-f]{20,}@.*", email):  # long hex strings
        return False
    if re.match(r".*@\d+\.\d+\.\d+$", email):  # version-like
        return False
    if re.search(r"\.(jpg|jpeg|png|gif|svg)$", email):  # image files
        return False
    return True

def fetch_emails_bs(url):
    emails = set()
    try:
        print(f"\n🔍 Checking: {url}")
        resp = requests.get(url, timeout=10, headers={"User-Agent": CUSTOM_UA})
        if resp.status_code != 200:
            return emails
        found = re.findall(EMAIL_REGEX, resp.text)
        emails.update(e.lower() for e in found if is_valid_email(e))
        print("📧 Emails found")
    except:
        pass
    return emails

def fetch_emails_uc(url):
    emails = set()
    try:
        driver = init_driver(headless=True)
        driver.get(url)
        time.sleep(2)
        found = re.findall(EMAIL_REGEX, driver.page_source)
        emails.update(e.lower() for e in found if is_valid_email(e))
        driver.quit()
        print("📧 Emails found")
    except:
        pass
    return emails

def extract_emails_from_links():
    ensure_email_csv()  # make sure CSV exists
    with open(EVENTS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Event Name", "").strip()
            date = row.get("Event Date", "").strip()
            if not name or not date:
                continue
            if email_already_saved(name, date):
                continue
            websites = row.get("Links", "").split(" | ")
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
                    if not is_valid_email(email):
                        continue
                    save_email_row([
                        name, date, site, email,
                        "", "", ""
                    ])
# -------------------- PHASE 3: uploading data on Gsheet --------------------
# === CONFIG ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS_EMAIL_CSV = os.path.join(SCRIPT_DIR, "events_email.csv")
UPLOADED_DATA_CSV = os.path.join(SCRIPT_DIR, "uploaded_data.csv")
SHEET_TOKEN = "13fEOnuQKBTMPkhwr-OmI84kbsDq-jup_mnv9CcOxhlo"  # Your sheet token
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "credentials.json")  # Your Google API credentials

# === LOAD UPLOADED DATA CSV (CREATE IF NOT EXISTS) ===
if not os.path.exists(UPLOADED_DATA_CSV):
    with open(UPLOADED_DATA_CSV, "w", newline="", encoding="utf-8") as f:
        pass  # create empty file

def load_uploaded_data():
    uploaded = set()
    with open(UPLOADED_DATA_CSV, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                uploaded.add(tuple(row))  # store as tuple for exact match
    return uploaded

def append_to_uploaded_data(rows):
    with open(UPLOADED_DATA_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)

# === GOOGLE SHEETS CONNECTION ===
def connect_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_TOKEN).sheet1
    return sheet

# === UPLOAD FUNCTION ===
def upload_new_data():
    uploaded_set = load_uploaded_data()
    new_rows = []

    # Read events_email.csv
    with open(EVENTS_EMAIL_CSV, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)  # Skip header
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

    # Connect to sheet
    sheet = connect_google_sheet()

    # Append each row to the sheet
    for row in new_rows:
        sheet.append_row(list(row))
        print(f"✅ Uploaded: {row[0]} ({row[1]})")  # Event Name & Date

    # Save to uploaded_data.csv so we don’t re-upload
    append_to_uploaded_data(new_rows)
    print("💾 Uploaded rows saved to uploaded_data.csv")
    
def highlight_duplicates():
    """
    Highlights duplicate rows in the Google Sheet based on:
    Event Name, Event Date, Website link, Email Address
    """
    sheet = connect_google_sheet()
    # Get all values from the sheet
    all_values = sheet.get_all_values()

    if not all_values or len(all_values) < 2:
        return  # nothing to check

    header = all_values[0]
    rows = all_values[1:]

    # Find indexes of the 4 key columns
    try:
        idx_name = header.index("Event Name")
        idx_date = header.index("Event Date")
        idx_website = header.index("Website link")
        idx_email = header.index("Email Address")
    except ValueError:
        print("⚠️ One or more key columns not found in the sheet")
        return

    seen = {}
    duplicates = []

    for i, row in enumerate(rows, start=2):  # start=2 because sheet rows start at 1 and row 1 is header
        key = (row[idx_name], row[idx_date], row[idx_website], row[idx_email])
        if key in seen:
            duplicates.append(i)         # current duplicate row
            duplicates.append(seen[key]) # first occurrence
        else:
            seen[key] = i
        time.sleep(2)

    # Remove duplicates from list
    duplicates = list(set(duplicates))

    # Apply red background to duplicates
    for row_number in duplicates:
        sheet.format(f"A{row_number}:{chr(64+len(header))}{row_number}", {
            "backgroundColor": {"red": 1, "green": 0.8, "blue": 0.8}
        })

    print(f"⚠️ Highlighted {len(duplicates)} duplicate rows in red.")

# -------------------- RUN --------------------
while True:
    fetch_and_test_proxies()
    proxies = load_proxies()

    while proxies:
        current_proxy = proxies[0]
        success = scrape_with_proxy(current_proxy)
        if success:
            break
        else:
            proxies.pop(0)
            save_proxies(proxies)

    extract_emails_from_links()
    upload_new_data()

    if not proxies:
        print("🚫 No proxies left.")
    upload_to_github()
    highlight_duplicates()
    # print("⏳ Sleeping for 2 hours...")
    # time.sleep(7200)  # Sleep for 2 hours
