import os
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError

USERNAME = os.getenv("SMARTFIND_USERNAME")
PASSWORD = os.getenv("SMARTFIND_PASSWORD")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

LOGIN_URL = "https://hrsubsfresnounified.eschoolsolutions.com/logOnInitAction.do"

# =========================
# CRITERIA (from accept.py)
# =========================
TARGET_KEYWORDS = [
    "middle school", "middle", "resource", "rsp",
    "high", "high school", "junior high",
    "grade 7", "grade 8", "grades 7", "grades 8",
    "7th grade", "8th grade",
    "ms ", " ms", " hs", " hs ",
    "jr high"
]

MIN_HOURS = 4.0


# =========================
# TELEGRAM
# =========================
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        response = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        })
        print("📨 Telegram:", response.status_code)
    except Exception as e:
        print("Telegram error:", e)


# =========================
# SAFE TEXT
# =========================
def safe_text(locator):
    try:
        if locator.count() > 0:
            return locator.first.inner_text().strip()
    except:
        pass
    return ""


# =========================
# TIME PARSER (from accept.py)
# =========================
def parse_hours(time_str):
    try:
        cleaned = time_str.replace("–", "-").replace("—", "-")
        parts = [p.strip() for p in cleaned.replace("-", " ").split() if p.strip()]

        time_tokens = [p for p in parts if ":" in p]
        ampm_tokens = [p for p in parts if p.upper() in ("AM", "PM")]

        if len(time_tokens) >= 2 and len(ampm_tokens) >= 2:
            t1 = f"{time_tokens[0]} {ampm_tokens[0]}"
            t2 = f"{time_tokens[1]} {ampm_tokens[1]}"

            fmt = "%I:%M %p"
            start = datetime.strptime(t1, fmt)
            end = datetime.strptime(t2, fmt)

            diff = (end - start).total_seconds() / 3600
            return diff if diff > 0 else diff + 24
    except:
        pass
    return 0.0


# =========================
# CRITERIA CHECK
# =========================
def matches_criteria(classification, location, time_str):
    combined = f"{classification} {location}".lower()

    keyword_match = any(k in combined for k in TARGET_KEYWORDS)
    if not keyword_match:
        print("   ❌ Keyword mismatch")
        return False

    hours = parse_hours(time_str)
    print(f"   ⏱ Hours detected: {hours:.2f}")

    if hours < MIN_HOURS:
        print(f"   ❌ Too short (<{MIN_HOURS}h)")
        return False

    print("   ✅ Criteria passed")
    return True


# =========================
# JOB SCRAPER
# =========================
def get_available_jobs(page):

    jobs = []

    rows = page.locator("tbody.mobile-table-body tr[id^='mobile-row-']")
    count = rows.count()

    print(f"📋 Found {count} job rows")

    for i in range(count):

        try:
            print(f"\n🔎 Processing job {i+1}/{count}")

            row = rows.nth(i)

            # expand
            try:
                row.locator("pds-icon[name*='caret-right']").click()
                page.wait_for_timeout(400)
                print("   ➜ Expanded row")
            except:
                print("   ➜ No expand needed")

            date = safe_text(row.locator("td[id*='startendDate']"))
            time_text = safe_text(row.locator("td[id*='startendtime']"))

            classification = safe_text(
                row.locator("td[id*='classification'], td[id*='classif']")
            )

            location = safe_text(
                row.locator("td[id*='location'], td[id*='school']")
            )

            print(f"   📅 {date}")
            print(f"   ⏰ {time_text}")
            print(f"   📚 {classification}")
            print(f"   🏫 {location}")

            expanded = page.locator(f"#mobile-row-expanded-{i}")
            if expanded.count() > 0:
                classification += " " + expanded.inner_text()
                location += " " + expanded.inner_text()

            jobs.append({
                "date": date,
                "time": time_text,
                "classification": classification,
                "location": location
            })

        except Exception as e:
            print("   ❌ Job error:", e)

    return jobs


# =========================
# MAIN CHECK
# =========================
def check_for_jobs():

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("\n🔐 Logging in...")
        page.goto(LOGIN_URL)

        page.fill("#userId", USERNAME)
        page.fill("#userPin", PASSWORD)
        page.click("#submitBtn")

        page.wait_for_selector("#available-tab", timeout=60000)
        print("✅ Login successful")

        print("📂 Opening Available Jobs tab...")
        page.click("#available-tab")
        page.wait_for_selector("#available-panel.pds-is-active", timeout=60000)

        print("⏳ Checking for jobs...")

        rows = page.locator("tbody.mobile-table-body tr[id^='mobile-row-']")
        row_count = rows.count()

        if row_count == 0:
            print("❌ No jobs found")
            browser.close()
            return

        send_telegram("🚨 Jobs available on SmartFind!")

        jobs = get_available_jobs(page)

        # =========================
        # AUTO ACCEPT LOGIC
        # =========================
        for i, job in enumerate(jobs):

            print(f"\n⚙️ Evaluating job {i+1}")

            if not matches_criteria(job["classification"], job["location"], job["time"]):
                print("⛔ Skipping job")
                continue

            print("🚀 Attempting ACCEPT...")

            try:
                row = rows.nth(i)

                accept_btn = row.locator("button:has-text('Accept'), [id*='accept']")
                if accept_btn.count() > 0:
                    accept_btn.first.click()
                    print("✔ Accept clicked")
                    page.wait_for_timeout(1000)

                    confirm = page.locator("#confirm-dialog")
                    if confirm.count() > 0:
                        confirm.first.click()
                        print("✔ Confirm clicked")
                        page.wait_for_timeout(1000)

                    print("🎉 JOB ACCEPTED")

            except Exception as e:
                print("❌ Accept failed:", e)

        browser.close()


# =========================
# LOOP
# =========================
print("🚀 Bot started")

while True:
    try:
        check_for_jobs()
    except Exception as e:
        print("💥 Error:", e)

    print("⏳ Waiting 20s...\n")
    time.sleep(20)
