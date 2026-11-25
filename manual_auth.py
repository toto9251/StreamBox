"""Manual login - checks first whether a session is already active."""

import json
import os
import sys
from pathlib import Path

from patchright.sync_api import sync_playwright

from pipeline import build_browser_context


def is_logged_in(page) -> bool:
    """Checks whether the user is already logged in."""
    try:
        content = page.content().lower()
        url = page.url.lower()

        if "/logout" in content or "logout" in content:
            return True
        if "/premium" in content and "account" in content:
            return True

        if url == "https://serienstream.to/" or url.endswith("/"):
            login_form = page.locator('form[action*="login"], form[action="/login"]')
            if login_form.count() == 0:
                return True

        return False
    except Exception:
        return False


def main():
    print("=" * 60)
    print("SERIENSTREAM LOGIN SETUP")
    print("=" * 60)
    print()

    auth_file = Path("auth_credentials.json")

    saved_email = None
    saved_password = None
    if auth_file.exists():
        try:
            with open(auth_file, "r", encoding="utf-8") as f:
                creds = json.load(f)
                saved_email = creds.get("email")
                saved_password = creds.get("password")
            print(f"[*] Found saved credentials: {saved_email}")
        except (json.JSONDecodeError, OSError):
            pass

    if saved_email:
        email = input(f"Email address [{saved_email}]: ").strip() or saved_email
    else:
        email = input("Email address: ").strip()

    if saved_password:
        password = input("Password [saved]: ").strip() or saved_password
    else:
        password = input("Password: ").strip()

    if not email or not password:
        print("[-] Email and password are required.")
        sys.exit(1)

    credentials = {"email": email, "password": password}
    with open(auth_file, "w", encoding="utf-8") as f:
        json.dump(credentials, f, indent=2)
    print(f"\n[+] Credentials saved to {auth_file}")

    print("\n[*] Opening browser...")
    user_data_dir = os.path.join(os.getcwd(), "playwright_data")

    with sync_playwright() as p:
        context = build_browser_context(p, user_data_dir)
        page = context.new_page()

        print("[*] Checking login status...")
        page.goto("https://serienstream.to/", wait_until="load", timeout=30000)
        page.wait_for_timeout(3000)

        if is_logged_in(page):
            print("[+] ALREADY LOGGED IN! Session is active.")
            print("[+] The browser profile stores your login.")
            print("\n[*] Keeping browser open for 10s for verification...")
            page.wait_for_timeout(10000)
            context.close()

            print("\n" + "=" * 60)
            print("SETUP SUCCESSFUL - NOTHING TO DO")
            print("=" * 60)
            print(f"Account: {email}")
            print("\nYou can now download episodes directly:")
            print("  python main.py https://serienstream.to/serie/...")
            return

        print("[*] Not logged in. Navigating to login page...")
        page.goto("https://serienstream.to/login", wait_until="load", timeout=30000)
        page.wait_for_timeout(3000)

        print("[*] Attempting automatic login...")

        email_filled = False
        for selector in ('input[name="email"]', 'input[type="email"]', 'input[id="email"]'):
            try:
                if page.locator(selector).count() > 0:
                    page.fill(selector, email)
                    email_filled = True
                    break
            except Exception:
                continue

        password_filled = False
        for selector in ('input[name="password"]', 'input[type="password"]', 'input[id="password"]'):
            try:
                if page.locator(selector).count() > 0:
                    page.fill(selector, password)
                    password_filled = True
                    break
            except Exception:
                continue

        button_clicked = False
        if email_filled and password_filled:
            button_selectors = (
                'button[type="submit"]',
                'button:has-text("Login")',
                'button:has-text("Anmelden")',
                'button:has-text("Einloggen")',
                'input[type="submit"]',
            )
            for selector in button_selectors:
                try:
                    if page.locator(selector).count() > 0:
                        page.click(selector)
                        button_clicked = True
                        break
                except Exception:
                    continue

        if email_filled and password_filled and button_clicked:
            print("[+] Automatic login submitted.")
        else:
            print("[!] Automatic login not possible.")
            print("[!] Please log in MANUALLY in the browser window.")

        print("\n[*] Waiting for login (max 180s)...")
        print("[!] Log in if needed. The browser window stays open.")

        logged_in = False
        for i in range(36):
            page.wait_for_timeout(5000)
            if is_logged_in(page):
                logged_in = True
                break
            print(f"  [{(i + 1) * 5}s] Not logged in yet...")

        if logged_in:
            print("\n[+] Login detected! Session saved.")
        else:
            print("\n[!] Timeout. Login may not have succeeded.")

        input("\n>>> Press ENTER to close...")
        context.close()

    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print(f"Account: {email}")
    print("\nYou can now download episodes:")
    print("  python main.py https://serienstream.to/serie/...")


if __name__ == "__main__":
    main()
