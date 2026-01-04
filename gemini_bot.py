#!/usr/bin/env python3
"""
ChatGPT Bot - Send prompts and fetch responses using logged-in session.
"""
import os
import sys
import time
import json
import traceback
from typing import Optional
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException
)


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
            if not self.headless:
                print("Initializing browser...")
            driver = uc.Chrome(options=options, use_subprocess=True)
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

    def _wait_for_chat_ready(self) -> bool:
        """Wait for ChatGPT chat interface to be ready."""
        try:
            print("Waiting 5 seconds for page to load...")
            time.sleep(5)
            print("✓ Wait complete, proceeding to enter prompt")
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

    def _find_send_button(self):
        """Find the send button."""
        # Try multiple selectors for the send button
        selectors = [
            "button[data-testid='send-button']",
            "button[aria-label*='Send']",
            "button[aria-label*='send']",
            "button[title*='Send']",
            "button[title*='send']",
            "button svg[data-icon='paper-plane']",
            "button:has(svg[data-icon='paper-plane'])",
            # Fallback: button near the textarea
            "textarea[data-id='root'] ~ button",
            "textarea#prompt-textarea ~ button",
        ]

        for selector in selectors:
            try:
                # Try to find button near the textarea
                if "~" in selector:
                    # Get textarea first
                    textarea = self._find_input_element()
                    # Find button in the same container
                    parent = textarea.find_element(By.XPATH, "./..")
                    buttons = parent.find_elements(By.TAG_NAME, "button")
                    for btn in buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            return btn
                else:
                    button = self.driver.find_element(
                        By.CSS_SELECTOR, selector)
                    if button.is_displayed() and button.is_enabled():
                        return button
            except (NoSuchElementException, Exception):
                continue

        raise NoSuchElementException("Could not find send button")

    def _send_prompt(self, prompt: str) -> bool:
        """Send a prompt to ChatGPT by entering text and clicking send."""
        try:
            print(f"Entering prompt: {prompt[:50]}...")

            # Find input element
            input_element = self._find_input_element()
            print("✓ Found input element")

            # Scroll to input element and ensure it's in view
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                input_element)
            time.sleep(0.5)

            # For headless mode, use JavaScript for everything
            if self.headless:
                # Focus using JavaScript
                self.driver.execute_script(
                    "arguments[0].focus();", input_element)
                self.driver.execute_script(
                    "arguments[0].click();", input_element)
                time.sleep(0.5)
                print("✓ Focused input (headless mode)")

                # In headless, always use JavaScript to set value
                text_entered = False
                try:
                    is_textarea = input_element.tag_name.lower() == 'textarea'
                    if is_textarea:
                        # Set value and trigger all necessary events
                        self.driver.execute_script(
                            "arguments[0].value = arguments[1];",
                            input_element, prompt)
                        # Trigger multiple events for better compatibility
                        self.driver.execute_script(
                            "arguments[0].dispatchEvent(new Event('input', "
                            "{ bubbles: true, cancelable: true }));",
                            input_element)
                        self.driver.execute_script(
                            "arguments[0].dispatchEvent(new Event('change', "
                            "{ bubbles: true, cancelable: true }));",
                            input_element)
                        self.driver.execute_script(
                            "arguments[0].dispatchEvent(new KeyboardEvent("
                            "'keyup', { bubbles: true, cancelable: true, "
                            "key: 'Enter' }));",
                            input_element)
                        text_entered = True
                        print("✓ Set text via JavaScript (headless mode)")
                except Exception as e:
                    print(f"⚠ JavaScript method failed: {e}")
            else:
                # Non-headless: try click first
                try:
                    input_element.click()
                    time.sleep(0.3)
                    print("✓ Clicked input to focus")
                except Exception as e:
                    print(f"⚠ Could not click input: {e}")

                # Try multiple methods to enter text
                text_entered = False

                # Method 1: Try JavaScript to set value (works for textarea)
                try:
                    is_textarea = input_element.tag_name.lower() == 'textarea'
                    if is_textarea:
                        self.driver.execute_script(
                            "arguments[0].value = arguments[1];",
                            input_element, prompt)
                        # Trigger input event
                        self.driver.execute_script(
                            "arguments[0].dispatchEvent(new Event('input', "
                            "{ bubbles: true }));",
                            input_element)
                        text_entered = True
                        print("✓ Set text via JavaScript (textarea)")
                except Exception as e:
                    print(f"⚠ JavaScript method failed: {e}")

            # Method 2: Try send_keys
            # (works for both textarea and contenteditable)
            if not text_entered:
                try:
                    # Clear first
                    input_element.clear()
                    time.sleep(0.2)

                    # Focus the element
                    self.driver.execute_script(
                        "arguments[0].focus();", input_element)
                    time.sleep(0.2)

                    # Send keys
                    input_element.send_keys(prompt)
                    text_entered = True
                    print("✓ Entered text via send_keys")
                except Exception as e:
                    print(f"⚠ send_keys failed: {e}")

            # Method 3: For contenteditable divs, use JavaScript
            if not text_entered:
                try:
                    contenteditable_attr = input_element.get_attribute(
                        'contenteditable')
                    is_contenteditable = contenteditable_attr == 'true'
                    if is_contenteditable:
                        self.driver.execute_script(
                            "arguments[0].innerText = arguments[1];",
                            input_element, prompt)
                        self.driver.execute_script(
                            "arguments[0].dispatchEvent(new Event('input', "
                            "{ bubbles: true }));",
                            input_element)
                        text_entered = True
                        print("✓ Set text via JavaScript (contenteditable)")
                except Exception as e:
                    print(f"⚠ Contenteditable method failed: {e}")

            if not text_entered:
                print("❌ Failed to enter text using any method",
                      file=sys.stderr)
                return False

            # Wait a bit for text to be processed
            time.sleep(0.5)

            # Verify text was entered
            try:
                if input_element.tag_name.lower() == 'textarea':
                    current_value = input_element.get_attribute('value')
                else:
                    current_value = input_element.text or \
                        input_element.get_attribute('innerText')
                if prompt[:20] not in (current_value or ''):
                    msg = "⚠ Warning: Text may not have been entered correctly"
                    print(msg)
                else:
                    print("✓ Verified text entered")
            except Exception:
                pass

            # Find and click the send button
            try:
                send_button = self._find_send_button()
                print("✓ Found send button")

                # Scroll to button
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    send_button)
                time.sleep(0.3)

                # Try clicking with JavaScript if regular click fails
                try:
                    send_button.click()
                    print("✓ Clicked send button")
                except Exception:
                    # Fallback: JavaScript click
                    self.driver.execute_script(
                        "arguments[0].click();", send_button)
                    print("✓ Clicked send button (JavaScript)")

            except NoSuchElementException:
                # Fallback: use Enter key
                print("⚠ Send button not found, using Enter key")
                input_element.send_keys(Keys.RETURN)

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
