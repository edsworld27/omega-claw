# main.py — Omega Claw Entry Point
import os
from dotenv import load_dotenv

load_dotenv()

from core.logging_setup import setup_logging
from db.database import init_db

def main():
    setup_logging()
    
    import logging
    
    # Check required env
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token or token == "FILL_ME_IN":
        logging.critical("=" * 60)
        logging.critical("TELEGRAM_BOT_TOKEN not configured!")
        logging.critical("")
        logging.critical("To fix this:")
        logging.critical("1. Open Telegram and message @BotFather")
        logging.critical("2. Send /newbot and follow the prompts")
        logging.critical("3. Copy the token into .env file")
        logging.critical("4. Also get your user ID from @userinfobot")
        logging.critical("5. Add it to TELEGRAM_ALLOWED_USER_IDS in .env")
        logging.critical("=" * 60)
        exit(1)
    
    # Initialize SQLite
    init_db()
    logging.info("🦀 Omega Claw: Database initialized.")
    
    # Boot the bot
    logging.info("🦀 Omega Claw: Starting Telegram interface...")
    from core.telegram_bot import run_bot
    try:
        run_bot()
    except Exception as e:
        logging.critical(f"Omega Claw failed: {e}", exc_info=True)
        exit(1)

if __name__ == "__main__":
    main()
