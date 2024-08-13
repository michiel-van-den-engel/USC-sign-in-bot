import os
import logging
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler

from usc_interface import USC_Interface

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
usc = USC_Interface(
    os.environ['UVA_USERNAME'],
    os.environ['UVA_PASSWORD'],
    uva_login=True
)

async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message that the user will now receive updates for the sport they choose"""
    user = update.effective_user

    await update.message.reply_html(
        rf"Heyhoy {user.mention_html()}, You are now receiving invites for training"
    )

async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message explaining what to do"""
    await update.mesage.reply_text(
        "We'll send you updates on all the trainings. You can sign up via the buttons. To "+
        "stop, use the /cancel command"
    )

async def message_handler(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Check for updates"""
    choice = await update.callback_query.data
    
    if choice:
        usc.sign_up_for_lesson()

    text_choice = "Yes" if choice else "No"

    await update.callback_query.edit_message_text(
        update.callback_query.message.text +
        f"\n\nWe have recorded your choice as being {text_choice}. Good luck!"
    )

def main() -> None:
    """Start the bot"""
    application = Application.builder().token(os.environ['BOTTOKEN']).build()

    # Add some handlers for commands that might occur
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    # Add a handler to handle the input from the buttons
    application.add_handler(CallbackQueryHandler(message_handler))

    # Now run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    load_dotenv()
    main()
