# to login to the Ai Chatbot
import os
import re
import time
import winreg
import subprocess
import traceback
from typing import Optional, Tuple
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException
)


def get_chrome_version() -> int:
    """Detect the installed Chrome major version from the Windows registry."""
    reg_paths = [
        (winreg.HKEY_CURRENT_USER,
         r"Software\Google\Chrome\BLBeacon"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Google\Chrome\BLBeacon"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Wow6432Node\Google\Chrome\BLBeacon"),
    ]
    for hive, path in reg_paths:
        try:
            key = winreg.OpenKey(hive, path)
            version, _ = winreg.QueryValueEx(key, "version")
            winreg.CloseKey(key)
            return int(version.split(".")[0])
        except Exception:
            continue

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in chrome_paths:
        if os.path.exists(path):
            try:
                out = subprocess.check_output(
                    [path, "--version"], stderr=subprocess.DEVNULL,
                    timeout=5).decode()
                m = re.search(r"(\d+)\.", out)
                if m:
                    return int(m.group(1))
            except Exception:
                continue

    raise RuntimeError("Could not detect Chrome version")


class ChatGPTLogin:
    """Optimized ChatGPT login handler with comprehensive error handling."""

    def __init__(self, profile_name: str = "Default"):
        """Initialize the login handler."""
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.profile_path = os.path.join(self.script_dir, "chrome-profile")
        self.profile_name = profile_name
        self.driver: Optional[uc.Chrome] = None
        self.max_retries = 3
        self.timeout = 30

    def _create_driver(self) -> uc.Chrome:
        """Create and configure the undetected Chrome driver."""
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={self.profile_path}")
        options.add_argument(f"--profile-directory={self.profile_name}")

        # Additional options for better compatibility
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        options.add_argument("--window-size=1920,1080")

        # Preferences
        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_setting_values.notifications": 2
        }
        options.add_experimental_option("prefs", prefs)

        try:
            chrome_ver = get_chrome_version()
            print(f"Initializing browser (Chrome {chrome_ver})...")
            driver = uc.Chrome(options=options, use_subprocess=True,
                               version_main=chrome_ver)
            driver.set_page_load_timeout(self.timeout)
            return driver
        except Exception as e:
            print(f"❌ Failed to create browser: {e}")
            raise

    def _check_cloudflare(self) -> Tuple[bool, str]:
        """Check if we're on a Cloudflare challenge page."""
        try:
            page_source = self.driver.page_source.lower()
            current_url = self.driver.current_url.lower()

            cf_indicators = [
                'cloudflare' in page_source,
                'checking your browser' in page_source,
                'just a moment' in page_source,
                'challenges.cloudflare.com' in current_url,
                'cf-browser-verification' in page_source,
                'ray id' in page_source
            ]

            if any(cf_indicators):
                return True, "Cloudflare challenge detected"
            return False, "Not on Cloudflare"
        except Exception:
            return False, "Unable to check Cloudflare status"

    def _check_login_state(self) -> Tuple[str, bool]:
        """
        Check the current login state.
        Returns: (state, is_ready)
        States: 'logged_in', 'login_page', 'signup_page', 'cloudflare', 'error'
        """
        try:
            current_url = self.driver.current_url.lower()
            page_source = self.driver.page_source.lower()

            # Check for Cloudflare first
            is_cf, _ = self._check_cloudflare()
            if is_cf:
                return 'cloudflare', False

            # Check if already logged in
            logged_in_indicators = [
                'chat' in current_url and 'chatgpt.com' in current_url,
                'conversation' in current_url,
                'textarea[placeholder*="message"]' in page_source,
                'data-testid="chat-input"' in page_source,
                'send-button' in page_source
            ]

            if any(logged_in_indicators):
                try:
                    # Try to find chat interface elements
                    WebDriverWait(self.driver, 5).until(
                        EC.any_of(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, "textarea")),
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, "[data-testid*='chat']"))
                        )
                    )
                    return 'logged_in', True
                except TimeoutException:
                    pass

            # Check for login page
            login_indicators = [
                'login' in current_url,
                'sign-in' in current_url,
                'input[type="email"]' in page_source,
                'input[type="password"]' in page_source,
                'log in' in page_source,
                'sign in' in page_source,
                'data-testid*="login"' in page_source
            ]

            if any(login_indicators):
                return 'login_page', True

            # Check for signup page
            signup_indicators = [
                'signup' in current_url,
                'sign-up' in current_url,
                'create account' in page_source,
                'sign up' in page_source
            ]

            if any(signup_indicators):
                return 'signup_page', True

            # Check for error pages
            title = self.driver.title.lower()
            error_indicators = [
                'error' in title,
                'not found' in title,
                '403' in page_source,
                '404' in page_source,
                '500' in page_source,
                'access denied' in page_source
            ]

            if any(error_indicators):
                return 'error', False

            # Default: assume page is loading or unknown state
            return 'unknown', False

        except Exception as e:
            print(f"⚠ Error checking login state: {e}")
            return 'error', False

    def _wait_for_page_load(self, max_wait: int = 30) -> bool:
        """Wait for page to load and handle Cloudflare."""
        try:
            # Wait for body to be present
            WebDriverWait(self.driver, max_wait).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Initial wait for Cloudflare
            print("Waiting for page to load...")
            time.sleep(3)

            # Check Cloudflare status
            is_cf, cf_msg = self._check_cloudflare()
            if is_cf:
                print(f"⚠ {cf_msg}")
                print("   Waiting for Cloudflare verification...")

                # Wait longer for Cloudflare to complete
                for i in range(5):
                    time.sleep(3)
                    is_cf, _ = self._check_cloudflare()
                    if not is_cf:
                        print("✓ Cloudflare check passed!")
                        break
                    print(f"   Still waiting... ({i+1}/5)")

                # Final check
                is_cf, _ = self._check_cloudflare()
                if is_cf:
                    print("⚠ Still on Cloudflare. Please complete "
                          "any challenge manually if visible.")
                    return False

            return True
        except TimeoutException:
            print("⚠ Page load timeout. Checking current state...")
            return False
        except Exception as e:
            print(f"⚠ Error waiting for page: {e}")
            return False

    def _verify_cookies(self) -> Tuple[bool, int]:
        """Verify that ChatGPT cookies are present."""
        try:
            cookies = self.driver.get_cookies()
            chatgpt_cookies = [
                c for c in cookies
                if any(domain in c.get('domain', '') for domain in
                       ['openai.com', 'chatgpt.com', '.openai.com'])
            ]
            return len(chatgpt_cookies) > 0, len(chatgpt_cookies)
        except Exception as e:
            print(f"⚠ Error checking cookies: {e}")
            return False, 0

    def _navigate_to_chatgpt(self) -> bool:
        """Navigate to ChatGPT with retry logic."""
        urls_to_try = [
            "https://www.chatgpt.com/",
            "https://chat.openai.com/",
            "https://chatgpt.com/auth/login"
        ]

        for attempt in range(self.max_retries):
            for url in urls_to_try:
                try:
                    print(f"Attempting to open: {url}")
                    self.driver.get(url)
                    if self._wait_for_page_load():
                        return True
                except TimeoutException:
                    print(f"⚠ Timeout loading {url}")
                    continue
                except WebDriverException as e:
                    print(f"⚠ Network error: {e}")
                    if attempt < self.max_retries - 1:
                        retry_msg = (
                            f"   Retrying in 3 seconds... "
                            f"({attempt+1}/{self.max_retries})"
                        )
                        print(retry_msg)
                        time.sleep(3)
                    continue

        return False

    def login(self) -> bool:
        """Main login method with comprehensive error handling."""
        try:
            # Create driver
            self.driver = self._create_driver()

            # Navigate to ChatGPT
            if not self._navigate_to_chatgpt():
                print("❌ Failed to load ChatGPT after multiple attempts")
                return False

            # Check current state
            state, is_ready = self._check_login_state()
            print(f"\n📊 Current state: {state}")

            if state == 'logged_in':
                print("✓ Already logged in! Session is active.")
                has_cookies, cookie_count = self._verify_cookies()
                if has_cookies:
                    print(f"✓ Verified {cookie_count} session cookies")
                return True

            elif state == 'login_page':
                print("✓ Login page detected. Please log in manually.")
                print("   Waiting for you to complete login...")

                # Wait for login to complete
                for i in range(60):  # Wait up to 5 minutes
                    time.sleep(5)
                    new_state, _ = self._check_login_state()
                    if new_state == 'logged_in':
                        print("✓ Login successful!")
                        has_cookies, cookie_count = self._verify_cookies()
                        if has_cookies:
                            print(f"✓ Verified {cookie_count} session cookies")
                        return True
                    elif new_state != 'login_page':
                        print(f"⚠ State changed to: {new_state}")
                        break
                    if i % 6 == 0:  # Every 30 seconds
                        print("   Still waiting for login...")

            elif state == 'cloudflare':
                print("⚠ Still on Cloudflare challenge page.")
                print("   Please complete any challenge manually.")
                input("   Press ENTER after completing Cloudflare...")
                # Re-check state
                state, _ = self._check_login_state()
                if state == 'logged_in':
                    print("✓ Login successful!")
                    return True

            elif state == 'error':
                print("⚠ Error page detected. Please check the browser.")
                print(f"   Current URL: {self.driver.current_url}")

            else:
                print("⚠ Unknown page state. Please check the browser "
                      "manually.")
                print(f"   Current URL: {self.driver.current_url}")

            # Final verification
            has_cookies, cookie_count = self._verify_cookies()
            if has_cookies:
                print(f"\n✓ Found {cookie_count} ChatGPT cookies - "
                      "session will be saved!")
            else:
                print("\n⚠ Warning: No ChatGPT cookies found. "
                      "Session may not persist.")

            return has_cookies

        except KeyboardInterrupt:
            print("\n⚠ Interrupted by user")
            return False
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            traceback.print_exc()
            return False

    def close(self):
        """Safely close the browser."""
        if self.driver:
            try:
                print("\nClosing browser...")
                time.sleep(1)  # Give time for cookies to save
                self.driver.quit()
                print("✓ Browser closed successfully")
            except Exception as e:
                print(f"⚠ Error closing browser: {e}")
                try:
                    self.driver.quit()
                except Exception:
                    pass


def main():
    """Main entry point."""
    print("=" * 60)
    print("ChatGPT Login Script - Optimized Version")
    print("=" * 60)

    login_handler = ChatGPTLogin()

    try:
        success = login_handler.login()

        if success:
            print("\n" + "=" * 60)
            print("✓ Login process completed successfully!")
            print("  Session data saved to chrome-profile/Default/")
            msg = ("  Next time you run this script, you should remain "
                   "logged in.")
            print(msg)
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("⚠ Login process completed with warnings.")
            print("  Please check the browser window for any issues.")
            print("=" * 60)

        input("\nPress ENTER to close the browser...")

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        traceback.print_exc()
        input("Press ENTER to exit...")
    finally:
        login_handler.close()


if __name__ == "__main__":
    main()
