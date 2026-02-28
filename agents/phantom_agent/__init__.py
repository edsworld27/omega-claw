# agents/phantom_agent/__init__.py
# Vector 2: The Phantom Engine (GUI Automation & Computer Vision)
# CONFIRMED WORKING: osascript focus + pyautogui typing tested successfully.

import pyautogui
import subprocess
import time
import logging
import os
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# SECURITY WARNING: This script takes physical control of the host machine's mouse and keyboard.
# The user must not touch the machine while Vector 2 is executing.


class PhantomAgent:
    """
    The Ghost Agent. Controls the Antigravity IDE desktop app by:
    1. Stealing window focus via AppleScript
    2. Physically typing prompts via PyAutoGUI
    3. Watching the screen via OCR for "Allow" buttons and rate limit warnings
    4. Auto-clicking model dropdowns to swap engines when limits are hit
    """

    # Keywords the Vision Loop watches for
    ALLOW_KEYWORDS = ["allow", "approve", "accept", "yes, allow"]
    LIMIT_KEYWORDS = ["usage limit", "rate limit", "run out of messages", "limit reached", "try again later"]
    CRASH_KEYWORDS = ["not responding", "keep waiting", "wait", "unresponsive"]
    DONE_KEYWORDS = ["task completed", "finished", "done", "all changes applied"]

    def __init__(self, target_app_name: str = "Antigravity", poll_interval: int = 5):
        self.target_app_name = target_app_name
        self.is_focused = False
        self.poll_interval = poll_interval  # seconds between vision scans
        self.running = False
        self._on_limit_callback: Optional[Callable] = None
        self._on_done_callback: Optional[Callable] = None
        self._landmarks = self._load_landmarks()

        # PyAutoGUI safety features
        pyautogui.FAILSAFE = True   # Move mouse to any corner to emergency abort
        pyautogui.PAUSE = 0.3       # Slight delay after every PyAutoGUI call

    def _load_landmarks(self) -> dict:
        """Load the UI coordinates from landmarks.json."""
        import json
        path = os.path.join(os.path.dirname(__file__), "landmarks.json")
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[Ghost] Failed to load landmarks: {e}")
            return {}

    def _get_landmark_coords(self, landmark_name: str):
        """Calculates absolute coordinates for a landmark based on second monitor detection."""
        layout = self._get_monitor_layout()
        # Default to primary if no secondary found
        screen = layout[0]
        res_key = f"{int(screen['w'])}x{int(screen['h'])}_primary"

        if len(layout) > 1:
            # Secondary monitor (usually the leftmost one as per earlier detection)
            screen = min(layout, key=lambda s: s["x"])
            res_key = f"{int(screen['w'])}x{int(screen['h'])}_secondary"
        
        landmarks = self._landmarks.get(res_key, {})
        data = landmarks.get(landmark_name)
        
        if not data:
            logger.warning(f"[Ghost] No landmark '{landmark_name}' for resolution {res_key}")
            # Fallback to secondary 1920x1080 defaults if possible
            data = self._landmarks.get("1920x1080_secondary", {}).get(landmark_name)

        if data:
            abs_x = screen["x"] + (screen["w"] * data["x_rel"])
            abs_y = screen["y"] + (screen["h"] * data["y_rel"])
            return int(abs_x), int(abs_y)
        
        return None

    # ─── WINDOW CONTROL ───────────────────────────────────────────

    def _get_monitor_layout(self):
        """Detects all connected screens and their frames using AppKit."""
        try:
            from AppKit import NSScreen
            screens = NSScreen.screens()
            layout = []
            for s in screens:
                f = s.frame()
                layout.append({
                    "x": f.origin.x,
                    "y": f.origin.y,
                    "w": f.size.width,
                    "h": f.size.height
                })
            return layout
        except Exception as e:
            logger.warning(f"[Ghost] Could not detect monitor layout: {e}")
            return [{"x": 0, "y": 0, "w": 1920, "h": 1080}]

    def wait_for_active(self, timeout_seconds: int = 30) -> bool:
        """
        Hardening Phase 4: Wait for the IDE to be ready for input.
        Uses OCR to look for the 'Claude Arrow' (>) or an empty input.
        """
        logger.info(f"[Ghost] Waiting for active cursor (timeout {timeout_seconds}s)...")
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            text = self._screenshot_to_text()
            # Look for common prompt indicators in Antigravity/Claude
            if ">" in text or "ask a question" in text or "type a message" in text:
                logger.info("[Ghost] IDE active state DETECTED.")
                return True
            
            # If we see "thinking" or "generating", we keep waiting
            if "thinking" in text or "processing" in text:
                logger.debug("[Ghost] IDE is still thinking...")
            
            time.sleep(2)
            
        logger.warning("[Ghost] Timeout waiting for active state. Proceeding anyway.")
        return False

    def force_window_resize(self, width_percent: float = 0.8, height_percent: float = 0.9) -> bool:
        """
        Uses AppleScript to force the IDE window to a specific percentage of the screen.
        This ensures Landmarks remain consistent.
        """
        logger.info(f"[Ghost] Forcing window resize for {self.target_app_name}...")
        
        # Get primary screen size via AppKit
        layout = self._get_monitor_layout()
        screen = layout[0] # Target primary monitor for resizing if full-screen logic fails
        
        target_w = int(screen["w"] * width_percent)
        target_h = int(screen["h"] * height_percent)
        target_x = int(screen["x"] + (screen["w"] - target_w) / 2)
        target_y = int(screen["y"] + (screen["h"] - target_h) / 2)

        script = f'''
        tell application "System Events"
            set processName to "{self.target_app_name}"
            if exists application process processName then
                set theWindow to window 1 of application process processName
                set position of theWindow to {{{target_x}, {target_y}}}
                set size of theWindow to {{{target_w}, {target_h}}}
                return "SUCCESS"
            else
                return "FAIL"
            end if
        end tell
        '''
        try:
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            if "SUCCESS" in result.stdout:
                logger.info(f"[Ghost] Window resized to {target_w}x{target_h}")
                time.sleep(1)
                return True
        except Exception as e:
            logger.error(f"[Ghost] Window resize failed: {e}")
        return False

    def force_focus(self) -> bool:
        """
        Uses raw AppleScript (osascript) via subprocess to find the target app and 
        force it to the absolute front of the screen.
        """
        logger.info(f"[Ghost] Attempting AppleScript focus on {self.target_app_name}")

        script = f'''
        tell application "System Events"
            if exists application process "{self.target_app_name}" then
                tell application "{self.target_app_name}" to activate
                return "SUCCESS"
            else
                return "FAIL"
            end if
        end tell
        '''

        try:
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            if "SUCCESS" in result.stdout:
                logger.info(f"[Ghost] Successfully stole focus for {self.target_app_name}")
                self.is_focused = True
                time.sleep(1)
                return True
            else:
                logger.error(f"[Ghost] Target App '{self.target_app_name}' is not running.")
                self.is_focused = False
                return False
        except Exception as e:
            logger.error(f"[Ghost] AppleScript execution failed: {e}")
            self.is_focused = False
            return False

    # ─── KEYBOARD INJECTION ───────────────────────────────────────

    def inject_prompt(self, prompt: str, focus_chat: bool = True, use_mouse: bool = False):
        """
        Physically types the prompt into the active textbox and hits Enter.
        
        Args:
            prompt: The text string to inject.
            focus_chat: If True, sends Cmd+L before typing (default for IDEs).
            use_mouse: If True, attempts to click the bottom-right of the screen before typing.
        """
        if not self.is_focused:
            if not self.force_focus():
                raise Exception(f"Cannot inject prompt. {self.target_app_name} failed to focus.")

        # Hardening Phase 4: Wait for the IDE to be ready for input
        self.wait_for_active(timeout_seconds=60)

        logger.info(f"[Ghost] Preparing to inject: {prompt[:80]}...")
        
        if use_mouse:
            # Multi-monitor-aware mouse targeting
            layout = self._get_monitor_layout()
            # Default to the primary monitor if only one
            screen = layout[0]
            if len(layout) > 1:
                # Heuristic: the 'second' monitor is often where users put their IDE
                # or just use the one with the smallest origin.x (leftmost)
                screen = min(layout, key=lambda s: s["x"])
            
            # Click bottom-right of that specific screen
            target_x = screen["x"] + screen["w"] - 300
            target_y = screen["y"] + screen["h"] - 100
            logger.info(f"[Ghost] Moving mouse to target monitor at {target_x}, {target_y}")
            pyautogui.moveTo(target_x, target_y, duration=0.8)
            pyautogui.click()
            time.sleep(0.5)

        if focus_chat:
            # Most AI IDEs (Cursor/Antigravity/Windsurf) use Cmd+L or Cmd+K to focus chat
            logger.info("[Ghost] Sending focus shortcut (Cmd+L)")
            pyautogui.press('esc') # Clear any existing focus first
            time.sleep(0.2)
            pyautogui.hotkey('command', 'l')
            time.sleep(0.8) # Wait for UI transition and key release

        logger.info(f"[Ghost] Typing prompt into GUI...")
        pyautogui.write(prompt, interval=0.01)
        pyautogui.press('enter')
        logger.info("[Ghost] Prompt injected via ENTER key.")

    def accept_all_changes(self):
        """Clicks the 'Accept All' button in the IDE to commit file changes."""
        logger.info("[Ghost] Triggering 'Accept All' changes...")
        coords = self._get_landmark_coords("accept_all")
        if coords:
            pyautogui.moveTo(coords[0], coords[1], duration=0.5)
            pyautogui.click()
            logger.info(f"[Ghost] Clicked Accept All at {coords}")
        else:
            # Fallback: Many IDEs use Cmd+Shift+Enter to accept
            pyautogui.hotkey('command', 'shift', 'enter')
            logger.info("[Ghost] Fallback: Sent Cmd+Shift+Enter to accept changes.")

    def switch_model(self, model_index: int = 1):
        """Clicks the model selector and selects a different model."""
        logger.info(f"[Ghost] Switching model (index {model_index})...")
        coords = self._get_landmark_coords("model_selector")
        if coords:
            pyautogui.click(coords[0], coords[1])
            time.sleep(0.5)
            # Click the dropdown item. This is usually just below or in a list.
            # We'll click slightly above the selector for Gemini Pro (index 1)
            # or use arrow keys.
            for _ in range(model_index):
                pyautogui.press('up')
            pyautogui.press('enter')
            logger.info("[Ghost] Model switch completed.")
        else:
            logger.warning("[Ghost] Cannot switch model: No coordinates found.")

    def pause_generation(self):
        """Clicks the 'Stop' button in the IDE to pause AI generation."""
        logger.info("[Ghost] Attempting to pause generation...")
        coords = self._get_landmark_coords("stop_generation")
        if coords:
            pyautogui.click(coords[0], coords[1])
            logger.info(f"[Ghost] Clicked Stop Button at {coords}")
        else:
            # Fallback: Many Electron apps use Cmd+. to stop
            pyautogui.hotkey('command', '.')
            logger.info("[Ghost] Fallback: Sent Cmd+. to stop generation.")

    def prompt_external_ai(self, tool_name: str, instruction: str):
        """
        Physically prompts an external AI (NotebookLM/Gemini UI) on the secondary monitor.
        1. Switches focus to the AI tool.
        2. Types instruction into the AI's input area.
        3. Waits for completion.
        """
        logger.info(f"[Ghost] Prompting external AI '{tool_name}' with instruction...")
        
        # 1. Switch focus to the browser/AI tool
        # For now, we assume the AI tool is in a browser (e.g., Chrome or Safari)
        script = f'''
        tell application "System Events"
            if exists application process "Google Chrome" then
                tell application "Google Chrome" to activate
                return "SUCCESS"
            else if exists application process "Safari" then
                tell application "Safari" to activate
                return "SUCCESS"
            else
                return "FAIL"
            end if
        end tell
        '''
        subprocess.run(['osascript', '-e', script])
        time.sleep(1)

        # 2. Target secondary monitor + Click Input
        coords = self._get_landmark_coords("external_ai_input")
        if coords:
            pyautogui.click(coords[0], coords[1])
            time.sleep(0.5)
            # Clear input (Cmd+A -> Backspace)
            pyautogui.hotkey('command', 'a')
            pyautogui.press('backspace')
            
            # 3. Type Instruction
            pyautogui.write(instruction, interval=0.01)
            pyautogui.press('enter')
            logger.info("[Ghost] Instruction sent to external AI.")
        else:
            logger.error("[Ghost] Cannot find external AI input coordinates.")

    def extract_ai_artifact(self) -> str:
        """
        Extracts the generated artifact from the external AI.
        Uses a 'Select All + Copy' macro to grab text from the browser.
        Returns the captured text.
        """
        logger.info("[Ghost] Attempting to extract AI artifact via Clipboard...")
        # Macro: Click broadly in the content area -> Cmd+A -> Cmd+C
        coords = self._get_landmark_coords("external_ai_input") # Content is usually above input
        if coords:
            pyautogui.click(coords[0], coords[1] - 300) # Click content area
            time.sleep(0.5)
            pyautogui.hotkey('command', 'a')
            time.sleep(0.5)
            pyautogui.hotkey('command', 'c')
            time.sleep(0.5)
            
            # Read from clipboard
            import pyperclip
            try:
                content = pyperclip.paste()
                logger.info(f"[Ghost] Successfully captured artifact ({len(content)} chars).")
                return content
            except Exception as e:
                logger.error(f"[Ghost] Clipboard capture failed: {e}")
        return ""

    # ─── COMPUTER VISION (Screen OCR) ─────────────────────────────

    def _screenshot_to_text(self) -> str:
        """
        Takes a screenshot of the entire screen and runs OCR to extract all visible text.
        Returns the full extracted text as a lowercase string for keyword matching.
        """
        try:
            import pytesseract
            from PIL import Image

            # Take screenshot
            screenshot = pyautogui.screenshot()
            # Run OCR
            text = pytesseract.image_to_string(screenshot)
            return text.lower()
        except ImportError:
            logger.warning("[Ghost] pytesseract not available. Vision loop disabled.")
            return ""
        except Exception as e:
            logger.warning(f"[Ghost] OCR failed: {e}")
            return ""

    def _check_for_keywords(self, screen_text: str, keywords: list) -> bool:
        """Check if any keyword appears in the OCR'd screen text."""
        for keyword in keywords:
            if keyword in screen_text:
                logger.info(f"[Ghost] Detected keyword: '{keyword}'")
                return True
        return False

    # ─── MOUSE MACROS ─────────────────────────────────────────────

    def _click_allow_button(self):
        """
        When an 'Allow' popup is detected via OCR, use pyautogui to locate
        and click the button. Falls back to keyboard shortcut if not found.
        """
        logger.info("[Ghost] Attempting to click 'Allow' button...")
        try:
            # Try to find the button on screen using image recognition
            # For now, use keyboard shortcut as reliable fallback
            pyautogui.press('enter')  # Most Allow dialogs accept Enter
            logger.info("[Ghost] Pressed ENTER to approve permission.")
        except Exception as e:
            logger.error(f"[Ghost] Failed to click Allow: {e}")

    def _rotate_model(self):
        """
        When a rate limit is detected, trigger a mouse macro to rotate models.
        """
        logger.info("[Ghost] RATE LIMIT DETECTED — Initiating model rotation macro...")
        try:
            # 1. Clear any current error/focus
            pyautogui.press('esc')
            time.sleep(1)

            # 2. Switch to second model (e.g. Gemini Flash if Sonnet limit hit)
            self.switch_model(model_index=2) 
            time.sleep(1)

            # 3. Type 'Continue' to resume
            self.inject_prompt("Continue the task please.")
            logger.info("[Ghost] Model rotation macro complete.")
        except Exception as e:
            logger.error(f"[Ghost] Model rotation failed: {e}")

    # ─── THE MAIN VISION LOOP ─────────────────────────────────────

    def vision_watch_loop(self, on_limit: Callable = None, on_done: Callable = None, on_crash: Callable = None, max_idle_seconds: int = 600):
        """
        The core ghost loop. Runs continuously while the IDE is building.
        Updated: 600s (10m) idle timeout.
        """
        self._on_limit_callback = on_limit
        self._on_done_callback = on_done
        self._on_crash_callback = on_crash
        self.running = True

        logger.info(f"[Ghost] Vision watch loop STARTED. Polling every {self.poll_interval}s.")
        logger.info(f"[Ghost] Idle timeout: {max_idle_seconds}s (10m).")

        last_screen_text = ""
        idle_since = time.time()

        while self.running:
            try:
                time.sleep(self.poll_interval)

                # Screenshot + OCR
                screen_text = self._screenshot_to_text()
                if not screen_text:
                    continue

                # Check if screen changed (activity detection)
                if screen_text != last_screen_text:
                    idle_since = time.time()
                    last_screen_text = screen_text

                # Priority 1: Auto-approve permission requests
                if self._check_for_keywords(screen_text, self.ALLOW_KEYWORDS):
                    self._click_allow_button()
                    continue

                # Priority 2: Detect rate limits → rotate model
                if self._check_for_keywords(screen_text, self.LIMIT_KEYWORDS):
                    self._rotate_model()
                    if self._on_limit_callback:
                        self._on_limit_callback()
                    continue

                # Priority 2.5: Detect Crashes / Freezes
                if self._check_for_keywords(screen_text, self.CRASH_KEYWORDS):
                    self._click_keep_waiting()
                    if self._on_crash_callback:
                        self._on_crash_callback()
                    continue

                # Priority 3: Detect task completion
                if self._check_for_keywords(screen_text, self.DONE_KEYWORDS):
                    logger.info("[Ghost] Task appears COMPLETE.")
                    if self._on_done_callback:
                        self._on_done_callback()
                    self.running = False
                    break

                # Priority 4: Idle timeout
                elapsed_idle = time.time() - idle_since
                if elapsed_idle > max_idle_seconds:
                    logger.info(f"[Ghost] No screen activity for {max_idle_seconds}s. Assuming done.")
                    if self._on_done_callback:
                        self._on_done_callback()
                    self.running = False
                    break

            except pyautogui.FailSafeException:
                logger.critical("[Ghost] FAILSAFE TRIGGERED — Mouse moved to corner. Aborting.")
                self.running = False
                break
            except Exception as e:
                logger.error(f"[Ghost] Vision loop error: {e}")
                continue

        logger.info("[Ghost] Vision watch loop ENDED.")

    def stop(self):
        """Emergency stop for the vision loop."""
        logger.info("[Ghost] Stop signal received.")
        self.running = False


# ─── SANDBOX TEST ─────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("=" * 60)
    print("  PHANTOM AGENT (Ghost) — Sandbox Test")
    print("  Starting in 3 seconds. DO NOT TOUCH MOUSE.")
    print("  Move mouse to ANY CORNER to emergency abort.")
    print("=" * 60)
    time.sleep(3)

    agent = PhantomAgent("Terminal")
    if agent.force_focus():
        agent.inject_prompt("echo 'Vector 2 Ghost Agent is ALIVE'")
        print("\n✅ Ghost Agent: Focus stolen + prompt injected successfully.")
        print("Vision loop ready. Run with vision_watch_loop() for full autonomy.")
    else:
        print("\n❌ Ghost Agent: Could not focus target app.")
