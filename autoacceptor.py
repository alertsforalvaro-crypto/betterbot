import os
import time
import requests
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
 
        print("📋 Waiting for jobs state...")
 
        try:
            page.wait_for_function(
                """
                () => {
                    const hasRows = document.querySelectorAll(
                        "tbody.mobile-table-body tr[id^='mobile-row-']"
                    ).length > 0;
 
                    const noJobs = document.querySelector('#available-panel .pds-message-info')
                        ?.innerText
                        ?.toLowerCase()
                        .includes('no jobs');
 
                    return hasRows || noJobs;
                }
                """,
                timeout=60000
            )
        except TimeoutError:
            print("Timed out waiting for jobs state.")
            browser.close()
            return
 
        # --- REAL DETECTION ---
        rows = page.locator("tbody.mobile-table-body tr[id^='mobile-row-']")
        row_count = rows.count()
 
        if row_count == 0:
            print("❌ No job rows detected (avoiding false alert).")
            browser.close()
            return
 
        # Optional extra safety
        try:
            first_row_text = rows.nth(0).inner_text().strip()
            if not first_row_text:
                print("⚠️ Rows detected but empty — skipping alert.")
                browser.close()
                return
        except:
            pass
 
        print(f"✅ Jobs detected: {row_count}")
 
        # ✅ Send single alert
        send_telegram("🚨 Jobs available on SmartFind!")
 
        # =========================
        # AUTO ACCEPT LOGIC
        # =========================
        for i in range(row_count):
            print(f"\n🚀 Attempting ACCEPT on job {i+1}/{row_count}...")
 
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
                else:
                    print("⚠️ No accept button found for this job")
 
            except Exception as e:
                print("❌ Accept failed:", e)
 
        browser.close()
 
 
print("🚀 SmartFind Railway Bot Started")
 
while True:
 
    try:
        check_for_jobs()
 
    except Exception as e:
        print("Unexpected error:", e)
 
    print("⏳ Sleeping 20 seconds...\n")
 
    time.sleep(20)
