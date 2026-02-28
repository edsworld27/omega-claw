# core/telegram_bot.py — Omega Claw Telegram Interface
import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from core.orchestrator import Orchestrator

orchestrator = Orchestrator()

# Global reference to app for autonomous runner to send messages
_app = None
_autonomous_runner = None

# Authorized users
def _parse_allowed_users():
    raw = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
    users = []
    for uid in raw.split(","):
        uid = uid.strip()
        if uid and uid.isdigit():
            users.append(int(uid))
    return users

ALLOWED_USERS = _parse_allowed_users()

async def auth_check(update: Update) -> bool:
    """Reject unauthorized users. Deny-by-default per SECURITY.xml §5.4."""
    user_id = update.effective_user.id
    if not ALLOWED_USERS:
        logging.critical("SECURITY: ALLOWED_USERS is empty — denying ALL access. Set TELEGRAM_ALLOWED_USER_IDS in .env")
        await update.message.reply_text("⛔ Bot not configured. Contact admin.")
        return False
    if user_id not in ALLOWED_USERS:
        await update.message.reply_text("⛔ Unauthorized.")
        logging.warning(f"SECURITY: Unauthorized access attempt from user {user_id}")
        return False
    return True

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    if not await auth_check(update): return
    await update.message.reply_text(
        "🦀 **Omega Claw Online**\n\n"
        "I bridge your Telegram to the Omega Constitution Hive.\n\n"
        "**Commands:**\n"
        "• `start project` — Launch a new Omega build\n"
        "• `status` — Full Hive + job report\n"
        "• `inbox` — Pending Founder Jobs\n"
        "• `job history` — Past builds\n\n"
        "Just type naturally. I'll figure out the intent.",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route all text messages through the Orchestrator."""
    if not await auth_check(update): return
    
    user_text = update.message.text
    user_id = update.effective_user.id
    
    try:
        # Check wizard
        from db.database import get_wizard_state
        wizard_state = get_wizard_state(user_id)
        if wizard_state:
            from core.mcp_wizard import handle_wizard_input
            response = handle_wizard_input(user_id, user_text, wizard_state)
            if len(response) > 4000:
                for i in range(0, len(response), 4000):
                    await update.message.reply_text(response[i:i+4000], parse_mode="Markdown")
            else:
                await update.message.reply_text(response, parse_mode="Markdown")
            return

        response = await orchestrator.handle_message(user_id, user_text)
        # Split long messages for Telegram's 4096 char limit
        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await update.message.reply_text(response[i:i+4000], parse_mode="Markdown")
        else:
            await update.message.reply_text(response, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Message handling failed: {e}", exc_info=True)
        await update.message.reply_text("❌ Something went wrong. The error has been logged.")

async def handle_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mode command to set autonomy level."""
    if not await auth_check(update): return
    
    keyboard = [
        [InlineKeyboardButton("🟢 Full Autonomous", callback_data="mode:full")],
        [InlineKeyboardButton("🟡 Security Command", callback_data="mode:security")],
        [InlineKeyboardButton("🔴 Manual Override", callback_data="mode:manual")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    from db.database import get_autonomy_mode
    current_mode = get_autonomy_mode(update.effective_user.id)
    
    await update.message.reply_text(
        f"⚙️ **Autonomy Mode Settings**\n"
        f"Current Mode: `{current_mode.upper()}`\n\n"
        "Select a new mode to control how the TerminalAgent interacts with Claude Code:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def handle_mode_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle autonomy mode button presses."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in ALLOWED_USERS:
        return
        
    _, mode = query.data.split(":")
    
    from db.database import set_autonomy_mode
    set_autonomy_mode(user_id, mode)
    
    await query.edit_message_text(
        f"✅ Autonomy Mode successfully set to: **{mode.upper()}**",
        parse_mode="Markdown"
    )

async def send_telegram_message(user_id: int, message: str):
    """Send a message to a user via Telegram (used by autonomous runner)."""
    global _app
    if _app and user_id:
        try:
            await _app.bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Failed to send Telegram message: {e}")
    elif _app and ALLOWED_USERS:
        # If no specific user, send to first allowed user
        try:
            await _app.bot.send_message(chat_id=ALLOWED_USERS[0], text=message, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Failed to send Telegram message: {e}")


async def start_autonomous_runner():
    """Start the autonomous job runner in background."""
    global _autonomous_runner

    # Check if autonomous mode is enabled
    if os.getenv("OMEGA_AUTONOMOUS_MODE", "false").lower() != "true":
        logging.info("Autonomous mode disabled. Set OMEGA_AUTONOMOUS_MODE=true to enable.")
        return

    from core.autonomous_runner import AutonomousRunner
    _autonomous_runner = AutonomousRunner(telegram_callback=send_telegram_message)

    logging.info("🤖 Autonomous Runner starting...")
    asyncio.create_task(_autonomous_runner.start())


async def post_init(application):
    """Called after the bot is initialized."""
    global _app
    _app = application
    await start_autonomous_runner()


def run_bot():
    """Start the Telegram polling loop."""
    global _app

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logging.critical("TELEGRAM_BOT_TOKEN not set!")
        exit(1)

    app = ApplicationBuilder().token(token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("mode", handle_mode))
    app.add_handler(CallbackQueryHandler(handle_mode_callback, pattern="^mode:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    _app = app

    logging.info("🦀 Omega Claw is live on Telegram.")
    app.run_polling()
