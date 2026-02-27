#!/usr/bin/env python3
"""
OMEGA WATCHDOG — Rate Limit Failover Monitor

This script monitors a Claude terminal log file or process.
If it detects a "429: Rate Limit" error, it instantly:
1. Triggers a "Save State" command.
2. Optional: Opens Gemini Omega Prompter via a macro.
"""

import time
import os
import sys

# Configuration
LOG_FILE_TO_WATCH = "claude_terminal.log"
POLL_INTERVAL_SECONDS = 5
RATE_LIMIT_TRIGGER = "429"
ERROR_TRIGGER = "Error:"
MAX_RETRIES = 3

def failover_action():
    """Executes the failover protocol when a rate limit is hit."""
    print("\n[WATCHDOG] 🚨 RATE LIMIT DETECTED! INITIATING FAILOVER...")
    
    # Example 1: Creating a signal file that Claude/Omega Claw can detect
    with open(".rate_limit_flag", "w") as f:
        f.write("RATE_LIMIT_HIT\n")
        
    # Example 2: Running a command to save state
    # os.system("claude /save_state")
    
    # Example 3: AppleScript to open a browser to Gemini (Mac only)
    try:
        if sys.platform == 'darwin':
            print("[WATCHDOG] Opening Gemini failover page...")
            applescript = '''
            tell application "Google Chrome"
                activate
                open location "https://gemini.google.com"
            end tell
            '''
            os.system(f"osascript -e '{applescript}'")
    except Exception as e:
        print(f"Failed to launch browser macro: {e}")
        
    print("[WATCHDOG] Failover complete. Entering sleep mode...")
    
    # Sleep to prevent rapid firing. Rate limits usually last a few hours.
    time.sleep(3600)

def tail_and_monitor(file_path):
    """Tails a file (like 'tail -f') looking for the trigger phrase."""
    
    if not os.path.exists(file_path):
        print(f"[WATCHDOG] Error: Log file {file_path} not found.")
        print(f"[WATCHDOG] Creating a dummy log file to watch...")
        with open(file_path, 'w') as f:
            f.write("Omega Watchdog initialized.\n")
            
    print(f"[WATCHDOG] Monitoring {file_path} every {POLL_INTERVAL_SECONDS} seconds...")
    print(f"[WATCHDOG] Rate limit trigger: '{RATE_LIMIT_TRIGGER}'")
    print(f"[WATCHDOG] Error limit trigger: '{ERROR_TRIGGER}' | Max Retries: {MAX_RETRIES}")
    
    consecutive_errors = 0
    
    with open(file_path, 'r') as f:
        # Move to the end of file
        f.seek(0, 2)
        
        while True:
            line = f.readline()
            
            if not line:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue
                
            # If the line contains our rate limit trigger
            if RATE_LIMIT_TRIGGER in line:
                print(f"[WATCHDOG] Trigger found in line: {line.strip()}")
                failover_action()
                
            # Check for generic execution errors to prevent infinite loops
            if ERROR_TRIGGER in line:
                consecutive_errors += 1
                if consecutive_errors >= MAX_RETRIES:
                    print(f"\n[WATCHDOG] 🛑 HARD THROTTLE REACHED: {MAX_RETRIES} consecutive errors detected.")
                    print("[WATCHDOG] Infinite loop suspected. Forcing Failover Protocol.")
                    failover_action()
                    consecutive_errors = 0 # Reset after failover
            
            # Reset consecutive errors if we see success markers (can be expanded)
            elif "Success" in line or "Completed" in line:
                consecutive_errors = 0

if __name__ == "__main__":
    # If a user passes a file argument, watch that instead
    watch_file = sys.argv[1] if len(sys.argv) > 1 else LOG_FILE_TO_WATCH
    
    try:
        tail_and_monitor(watch_file)
    except KeyboardInterrupt:
        print("\n[WATCHDOG] Shutting down.")
        sys.exit(0)
