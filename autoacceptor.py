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


def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        response = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message
            }
        )

        print("Telegram response:", response.status_code)

    except Exception as e:
        print("Telegram error:", e)


# --- SAFE TEXT ---
def safe_text(locator):
    try:
        if locator.count() > 0:
            return locator.first.inner_text().strip()
    except:
        pass
    return ""


# --- HOURS PARSER ---
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


# --- MATCH CRITERIA ---
TARGET_KEYWORDS = [
    "middle school", "middle", "resource", "rsp", "high",
    "7-8", "high school", "junior high", "grade 7", "grade 8",
    "grades 7", "grades 8", "7th grade", "8th grade",
    " ms", "ms ", " hs", "hs "
]

MIN_HOURS = 4.0


def matches_criteria(classification, location, time_str):
    combined = f"{classification} {location}".lower()

    if not any(kw in combined for kw in TARGET_KEYWORDS):
        return False

    hours = parse_hours(time_str)
    if hours < MIN_HOURS:
        return False

    return True


def check_for_jobs():

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("🔐 Logging in...")

        page.goto(LOGIN_URL)

        page.fill("#userId", USERNAME)
        page.fill("#userPin", PASSWORD)
        page.click("#submitBtn")

        page.wait_for_selector("#available-tab", timeout=60000)

        page.click("#available-tab")
        page.wait_for_selector("#available-panel.pds-is-active", timeout=60000)

        print("✅ Logged in. Starting refresh loop...\n")

        # --- REFRESH LOOP ---
        while True:

            try:
                page.reload()
                page.wait_for_timeout(2000)

                rows = page.locator("tbody.mobile-table-body tr[id^='mobile-row-']")
                row_count = rows.count()

                no_jobs = page.locator("#available-panel .pds-message-info")

                # --- STATE: JOBS AVAILABLE ---
                if row_count > 0:

                    print(f"✅ Jobs available: {row_count}")

                    send_telegram("🚨 Jobs available on SmartFind!")

                    # --- AUTO ACCEPT ---
                    for i in range(row_count):

                        try:
                            row = rows.nth(i)

                            # expand
                            try:
                                caret = row.locator("pds-icon[name*='caret']")
                                if caret.count() > 0:
                                    caret.first.click()
                                    page.wait_for_timeout(300)
                            except:
                                pass

                            time_text = safe_text(
                                row.locator("td[id*='startendtime']")
                            )

                            classification = safe_text(
                                row.locator("td[id*='classification']")
                            )

                            location = safe_text(
                                row.locator("td[id*='location']")
                            )

                            expanded = page.locator(f"#mobile-row-expanded-{i}")
                            if expanded.count() > 0:
                                extra = expanded.inner_text()
                                classification += " " + extra
                                location += " " + extra

                            if not matches_criteria(classification, location, time_text):
                                continue

                            # click accept
                            for sel in [
                                f"tr[id='mobile-row-{i}'] [id*='accept']",
                                f"tr[id='mobile-row-{i}'] button"
                            ]:
                                btn = page.locator(sel)
                                if btn.count() > 0:
                                    btn.first.click()
                                    page.wait_for_timeout(1500)
                                    break

                        except Exception as e:
                            print("Auto-accept error:", e)

                # --- STATE: NO JOBS ---
                elif no_jobs.count() > 0 and \
                        "no jobs" in no_jobs.first.inner_text().lower():

                    print("😴 No jobs available")

                # --- STATE: RATE LIMITED / EMPTY ---
                else:
                    print("⚠️ Nothing loaded (rate limited or empty state)")

            except Exception as e:
                print("Loop error:", e)

            print("⏳ Refreshing in 5 seconds...\n")
            time.sleep(5)


print("🚀 SmartFind Bot Started")

while True:

    try:
        check_for_jobs()

    except Exception as e:
        print("Unexpected error:", e)

    print("🔁 Restarting browser...\n")
    time.sleep(10)
