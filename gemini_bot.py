#!/usr/bin/env python3
"""
ChatGPT Bot - Send prompts and fetch responses using logged-in session.
"""
import os
import re
import sys
import time
import json
import winreg
import subprocess
import traceback
from typing import Optional
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException
)


def get_chrome_version() -> int:
    """Detect the installed Chrome major version from the Windows registry."""
    # Registry path written by Chrome on every update
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

    # Fallback: ask the chrome.exe binary directly
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


class ChatGPTBot:
    """ChatGPT bot for sending prompts and fetching responses."""

    def __init__(self, headless: bool = True, profile_name: str = "Default"):
        """Initialize the ChatGPT bot."""
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.profile_path = os.path.join(self.script_dir, "chrome-profile")
        self.profile_name = profile_name
        self.headless = headless
        self.driver: Optional[uc.Chrome] = None
        self.timeout = 30

    def _create_driver(self) -> uc.Chrome:
        """Create and configure the undetected Chrome driver."""
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={self.profile_path}")
        options.add_argument(f"--profile-directory={self.profile_name}")

        # Headless mode - improved configuration
        if self.headless:
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--start-maximized")
            # Important for headless mode
            options.add_argument("--disable-web-security")
            options.add_argument("--disable-features=VizDisplayCompositor")
            # Set a proper user agent for headless
            options.add_argument(
                "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )

        # Additional options for better compatibility
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-software-rasterizer")

        # Preferences
        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_setting_values.notifications": 2
        }
        options.add_experimental_option("prefs", prefs)

        try:
            chrome_ver = get_chrome_version()
            if not self.headless:
                print(f"Initializing browser (Chrome {chrome_ver})...")
            driver = uc.Chrome(options=options, use_subprocess=True,
                               version_main=chrome_ver)
            driver.set_page_load_timeout(self.timeout)
            return driver
        except Exception as e:
            print(f"❌ Failed to create browser: {e}", file=sys.stderr)
            raise

    def _navigate_to_chat(self) -> bool:
        """Navigate to ChatGPT chat interface."""
        urls_to_try = [
            "https://chat.openai.com/",
            "https://www.chatgpt.com/",
            "https://chatgpt.com/"
        ]

        for url in urls_to_try:
            try:
                if not self.headless:
                    print(f"Navigating to: {url}")
                self.driver.get(url)
                return True
            except (TimeoutException, WebDriverException) as e:
                if not self.headless:
                    print(f"⚠ Failed to load {url}: {e}")
                continue

        return False

    def _wait_for_full_page_load(self) -> bool:
        """Wait for the page to fully load."""
        try:
            # Wait for document ready state
            WebDriverWait(self.driver, self.timeout).until(
                lambda driver: driver.execute_script(
                    "return document.readyState") == "complete"
            )

            # Wait for body to be present
            WebDriverWait(self.driver, self.timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Additional wait for React/SPA to initialize
            time.sleep(2)

            return True
        except TimeoutException:
            return False

    def _check_rate_limit_dialog(self) -> bool:
        """Return True if the 'Too many requests' dialog is visible."""
        try:
            dialog = self.driver.find_element(
                By.CSS_SELECTOR, "div[role='dialog']")
            heading = dialog.find_element(By.TAG_NAME, "h2")
            return "too many requests" in heading.text.lower()
        except NoSuchElementException:
            return False

    def _dismiss_rate_limit_dialog(self) -> None:
        """Click the 'Got it' button to dismiss the rate limit dialog."""
        try:
            btn = self.driver.find_element(
                By.CSS_SELECTOR, "div[role='dialog'] button.btn-primary")
            self.driver.execute_script("arguments[0].click();", btn)
            print("✓ Dismissed rate limit dialog")
            time.sleep(1)
        except NoSuchElementException:
            pass

    def _wait_for_chat_ready(self) -> bool:
        """Wait for ChatGPT chat interface to be ready."""
        try:
            print("Waiting 5 seconds for page to load...")
            time.sleep(5)
            print("✓ Wait complete, proceeding to enter prompt")

            if self._check_rate_limit_dialog():
                print("⚠ Rate limit dialog detected — waiting 20 minutes before retrying...")
                time.sleep(20 * 60)
                self._navigate_to_chat()
                time.sleep(5)
                if self._check_rate_limit_dialog():
                    print("⚠ Rate limit dialog shown again — dismissing and continuing...")
                    self._dismiss_rate_limit_dialog()

            return True

        except Exception as e:
            print(f"❌ Error during wait: {e}", file=sys.stderr)
            return False

    def _find_input_element(self):
        """Find the ChatGPT input element using the specific ID."""
        try:
            # Use the specific ID: prompt-textarea
            element = self.driver.find_element(By.ID, "prompt-textarea")
            print("✓ Found input element by ID: prompt-textarea")
            return element
        except NoSuchElementException:
            # Fallback to CSS selector
            try:
                element = self.driver.find_element(
                    By.CSS_SELECTOR, "textarea#prompt-textarea")
                print("✓ Found input element by CSS: textarea#prompt-textarea")
                return element
            except NoSuchElementException:
                raise NoSuchElementException(
                    "Could not find textarea with ID 'prompt-textarea'")

    def _find_send_button(self, timeout: int = 8):
        """Wait for the send button to become enabled and return it."""
        selectors = [
            "button[data-testid='send-button']",
            "button[aria-label='Send prompt']",
            "button[aria-label*='Send']",
            "button[title*='Send']",
        ]
        for selector in selectors:
            try:
                btn = WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                return btn
            except (TimeoutException, NoSuchElementException):
                continue

        # Last resort: any enabled button inside the composer form
        try:
            textarea = self.driver.find_element(By.ID, "prompt-textarea")
            form = textarea.find_element(
                By.XPATH, "ancestor::form[1] | ancestor::div[@role='textbox'][1]/..")
            buttons = form.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                if btn.is_displayed() and btn.is_enabled():
                    return btn
        except Exception:
            pass

        raise NoSuchElementException("Could not find send button")

    def _send_prompt(self, prompt: str) -> bool:
        """Send a prompt to ChatGPT by entering text and clicking send."""
        try:
            print(f"Entering prompt: {prompt[:50]}...")

            input_element = self._find_input_element()
            print("✓ Found input element")

            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                input_element)
            time.sleep(0.3)

            # Use ActionChains to click — this properly activates the element
            # so React recognises subsequent key events (unlike JS focus alone)
            actions = ActionChains(self.driver)
            actions.click(input_element).perform()
            time.sleep(0.3)

            # Clear existing content
            actions = ActionChains(self.driver)
            actions.key_down(Keys.CONTROL).send_keys("a").key_up(
                Keys.CONTROL).send_keys(Keys.DELETE).perform()
            time.sleep(0.2)

            # Type text — ActionChains sends to the active element
            actions = ActionChains(self.driver)
            actions.send_keys(prompt).perform()
            print("✓ Entered text via ActionChains")
            time.sleep(0.5)

            # Try to click the send button
            try:
                send_button = self._find_send_button(timeout=8)
                print("✓ Found send button")
                self.driver.execute_script(
                    "arguments[0].click();", send_button)
                print("✓ Clicked send button")
            except NoSuchElementException:
                # Fallback: send Enter via ActionChains to the active element
                print("⚠ Send button not found, using Enter key")
                actions = ActionChains(self.driver)
                actions.send_keys(Keys.RETURN).perform()

            print("✓ Prompt sent, waiting for response...")
            return True

        except Exception as e:
            print(f"❌ Failed to send prompt: {e}", file=sys.stderr)
            traceback.print_exc()
            return False

    def _wait_for_response_complete(self, max_wait: int = 120) -> bool:
        """Wait for ChatGPT response to fully complete."""
        try:
            print("Waiting for response to start...")

            # Wait for response to start appearing
            response_selectors = [
                "[data-message-author-role='assistant']",
                "[data-testid*='conversation-turn']",
                ".markdown",
            ]

            response_started = False
            for selector in response_selectors:
                try:
                    WebDriverWait(self.driver, 30).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, selector))
                    )
                    response_started = True
                    print("✓ Response started")
                    break
                except TimeoutException:
                    continue

            if not response_started:
                print("⚠ Response did not start", file=sys.stderr)
                return False

            # Wait for streaming to complete
            print("Waiting for response to complete...")
            start_time = time.time()

            while time.time() - start_time < max_wait:
                try:
                    # Check for stop button (indicates streaming)
                    stop_selectors = [
                        "button[aria-label*='Stop']",
                        "button[title*='Stop']",
                        "button[data-testid='stop-button']",
                    ]

                    stop_button_found = False
                    for selector in stop_selectors:
                        try:
                            stop_btn = self.driver.find_element(
                                By.CSS_SELECTOR, selector)
                            if stop_btn.is_displayed():
                                stop_button_found = True
                                break
                        except NoSuchElementException:
                            continue

                    if not stop_button_found:
                        # No stop button means streaming is complete
                        # Wait a bit more to ensure everything is rendered
                        time.sleep(2)
                        print("✓ Response completed")
                        return True

                    # Still streaming, wait a bit
                    time.sleep(1)

                except Exception:
                    # If we can't check, wait a bit and assume done
                    time.sleep(2)
                    break

            # Final check: wait a bit more for any final rendering
            time.sleep(2)
            print("✓ Response should be complete")
            return True

        except Exception as e:
            print(f"⚠ Error waiting for response: {e}", file=sys.stderr)
            # Still try to extract
            time.sleep(3)
            return False

    def _extract_response(self) -> str:
        """Extract the latest response from ChatGPT."""
        try:
            print("Extracting response...")

            # Try multiple selectors to find the response
            selectors = [
                "[data-message-author-role='assistant'] .markdown",
                "[data-message-author-role='assistant'] .prose",
                "[data-testid*='conversation-turn'] .markdown",
                "[data-testid*='conversation-turn'] .prose",
                "[data-message-author-role='assistant']",
            ]

            for selector in selectors:
                try:
                    elements = self.driver.find_elements(
                        By.CSS_SELECTOR, selector
                    )
                    if elements:
                        # Get the last (most recent) response
                        response = elements[-1].text.strip()
                        # Ensure meaningful content
                        if response and len(response) > 10:
                            msg = (f"✓ Extracted response "
                                   f"({len(response)} chars)")
                            print(msg)
                            return response
                except Exception:
                    continue

            # Fallback: try to get all assistant messages
            try:
                selector = "[data-message-author-role='assistant']"
                assistant_messages = self.driver.find_elements(
                    By.CSS_SELECTOR, selector
                )
                if assistant_messages:
                    response = assistant_messages[-1].text.strip()
                    if response:
                        msg = (f"✓ Extracted response (fallback, "
                               f"{len(response)} chars)")
                        print(msg)
                        return response
            except Exception:
                pass

            print("⚠ Could not extract response", file=sys.stderr)
            return ""

        except Exception as e:
            print(f"⚠ Error extracting response: {e}", file=sys.stderr)
            return ""

    def send_message(self, prompt: str) -> Optional[str]:
        """
        Send a message to ChatGPT and get the response.

        Args:
            prompt: The message to send to ChatGPT

        Returns:
            The response text, or None if failed
        """
        try:
            # Create driver
            self.driver = self._create_driver()

            # Navigate to ChatGPT
            if not self._navigate_to_chat():
                print("❌ Failed to navigate to ChatGPT", file=sys.stderr)
                return None

            # Wait for chat to be ready
            if not self._wait_for_chat_ready():
                print("❌ ChatGPT chat interface not ready", file=sys.stderr)
                return None

            # Send the prompt
            if not self._send_prompt(prompt):
                return None

            # Wait for response to complete
            if not self._wait_for_response_complete():
                print("⚠ Response timeout, attempting to extract anyway...",
                      file=sys.stderr)

            # Extract response
            response = self._extract_response()
            return response if response else None

        except KeyboardInterrupt:
            print("\n⚠ Interrupted by user", file=sys.stderr)
            return None
        except Exception as e:
            print(f"❌ Unexpected error: {e}", file=sys.stderr)
            if not self.headless:
                traceback.print_exc()
            return None
        finally:
            self.close()

    def close(self):
        """Safely close the browser."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass


def main():
    """Main entry point."""
    # Get prompt from command line or use default
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        prompt = "What is the capital of France?"

    # Create bot (headless by default, set to False for debugging)
    bot = ChatGPTBot(headless=True)

    # Send message and get response
    response = bot.send_message(prompt)

    # Output as JSON
    if response:
        output = {"response": response, "success": True}
    else:
        output = {
            "response": "",
            "success": False,
            "error": "Failed to get response from ChatGPT"
        }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
