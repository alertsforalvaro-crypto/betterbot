from playwright.sync_api import sync_playwright
import time
import requests
import os
from dotenv import load_dotenv

# =====================
# LOAD ENV
# =====================
load_dotenv()

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 30))


# =====================
# TELEGRAM (UNCHANGED)
# =====================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})


# =====================
# SAFE TEXT (UNCHANGED)
# =====================
def safe_text(locator):
    try:
        return locator.inner_text().strip()
    except:
        return None


# =====================
# MAIN LOOP
# =====================
def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # LOGIN (UNCHANGED)
        page.goto(os.getenv("LOGIN_URL"))

        page.fill("input[name='username']", USERNAME)
        page.fill("input[name='password']", PASSWORD)
        page.click("button[type='submit']")

        page.wait_for_load_state("networkidle")

        print("Logged in.")

        while True:
            try:
                page.reload()
                page.wait_for_timeout(3000)

                rows = page.locator("tr")
                row_count = rows.count()

                if row_count == 0:
                    print("No jobs found.")
                else:
                    print(f"{row_count} jobs found.")
                    send_telegram(f"{row_count} job(s) found!")

                    for i in range(row_count):
                        row = rows.nth(i)

                        # ORIGINAL FIELD EXTRACTION
                        date = safe_text(row.locator(".date"))
                        time_ = safe_text(row.locator(".time"))
                        location = safe_text(row.locator(".location"))
                        instructions = safe_text(row.locator(".instructions"))

                        print(date, time_, location)

                        # =====================
                        # 🔥 AUTO-ACCEPT (ONLY ADDITION)
                        # =====================
                        try:
                            accept_btn = row.locator("button:has-text('Accept')")

                            if accept_btn.count() > 0:
                                accept_btn.first.click()
                                print("Clicked Accept")

                                page.wait_for_timeout(1000)

                                confirm = page.locator("button:has-text('Confirm')")
                                if confirm.count() > 0:
                                    confirm.first.click()
                                    print("Confirmed acceptance")

                                send_telegram(
                                    f"Job accepted ✅\n{date} {time_} @ {location}"
                                )

                                break  # prevent spam clicking

                        except Exception as e:
                            print("Accept failed:", e)

                time.sleep(CHECK_INTERVAL)

            except Exception as e:
                print("Error:", e)
                time.sleep(5)


# run immediately (same behavior as your originals)
run()
