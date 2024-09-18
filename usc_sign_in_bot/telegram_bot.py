import os
import logging
import traceback
from datetime import datetime as dt
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes, MessageHandler, 
    filters, CallbackQueryHandler, ConversationHandler, CallbackContext)

from usc_sign_in_bot.usc_interface import UscInterface
from usc_sign_in_bot.db_helpers import UscDataBase
from usc_sign_in_bot.encryptor import Encryptor

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

# Define states for the conversation
LOGIN_METHOD, SPORT, USERNAME, PASSWORD, WRAP_UP,*_ = range(50)
LOGIN_METHODS = ['uva']

logger = logging.getLogger(__name__)

class TelegramBot():

    def __init__(self) -> None:
        """Start the bot"""
        self.app = Application.builder().token(os.environ['BOTTOKEN']).build()
        self.db = UscDataBase()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                LOGIN_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_sports)],
                SPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_username)],
                USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.ask_password)],
                PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.finish_sign_up)]
            },
            fallbacks=[CommandHandler('cancel_setup', self.cancel_setup)]
        )

        # Add some handlers for commands that might occur
        self.app.add_handler(conv_handler)
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CallbackQueryHandler(self.message_handler))

        # Also add an error handler for if something goes wrong
        self.app.add_error_handler(self.error_handler)

        # Now run the bot
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

    @staticmethod
    async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message that the user will now receive updates for the sport they choose"""
        user = update.effective_user

        await update.message.reply_html(
            rf"Heyhoy {user.mention_html()}, Welcome in our service for USC sports. To start, "+
            rf"I need some info from you. What login method would you like to use? You can try ({', '.join(LOGIN_METHODS)})"
        )

        logger.info("A user with telegram_id %s started sign up", user.id)
        return LOGIN_METHOD

    async def ask_sports(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Get the sport of the user, now ask for the Username"""
        login_method = update.message.text.strip(' ').lower()
        telegram_id = update.effective_user.id

        if login_method not in LOGIN_METHODS:
            raise ValueError("Login method is not known")

        user_id = self.db.insert_user(telegram_id, dt.now(), login_method)

        await update.message.reply_html(f"Allright, we registered {login_method} now we need to know "+
            "the sport you want to participate in. Note that spelling (including captial letters) is "+
            "very important here as this is where we will search for.")
        logger.info("Asked for the sport to user %s", user_id)
        
        return SPORT

    async def ask_username(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        """Get the sport of the user, now ask for the Username"""
        sport = update.message.text
        telegram_id = update.effective_user.id

        self.db.edit_data_point(telegram_id, "sport", sport, table="users", key_column="telegram_id")

        await update.message.reply_html(
            "Because the way this scraper work, we need to be able to log in on your behalf. If you don't feel "+
            "confertable doing that, please type /cancel_setup. You should either way make sure that you don't use this "+
            "password in more places. Now please type in your username that you use to log in. If you login with UVA, "+
            "this will be your uva email adress."
        )

        logger.info("Asked for the username to user with telegram_id %s", telegram_id)
        return USERNAME

    async def ask_password(self, update: Update, _: CallbackContext) -> None:
        username = update.message.text
        telegram_id = update.effective_user.id

        self.db.edit_data_point(telegram_id, "username", username, table="users", key_column="telegram_id")

        await update.message.reply_html("and now type in the password:")
        logger.info("Asked for the password to user with telegram_id %s", telegram_id)
        return PASSWORD

    async def finish_sign_up(self, update: Update, _: CallbackContext) -> None:
        password = update.message.text
        telegram_id = update.effective_user.id
        
        # Note: I know this is not a safe approach. This is not to be used as a commerce application but as a scraper
        # for private use. This approach makes that we need to store the passwords in a way that we can retrieve them
        # later. We are aware that this is an issue but since this is for private use ONLY we are okay with it. This is
        # a reminder to not reuse your passwords.
        encryptor = Encryptor(os.environ.get("ENCRYPT_KEY"))
        password_encrypt = encryptor.encrypt_data(password)
        self.db.edit_data_point(telegram_id, "password", password_encrypt, table="users", key_column="telegram_id")

        await update.message.reply_html("You have finished the sign up process. Many love from us and we hope to see you "+
            "in the gym! &#10084;")

        logger.info("Finsihed login process for user with telegram_id %s", telegram_id)
        return ConversationHandler.END

    @staticmethod
    async def cancel_setup(update: Update, _: CallbackContext) -> None:
        update.message.reply_text("Canceled signup, Type /start to start over")

        logger.info("User with telegram_id %s cancled the sign_on process", update.effective_user.id)
        return ConversationHandler.END

    @staticmethod
    async def help_command(update: Update, _: CallbackContext) -> None:
        """Send a message explaining what to do"""
        print(update)
        print(update.message)
        print(update.message.reply_text)
        await update.message.reply_text(
            "We'll send you updates on all the trainings. You can sign up via the buttons. To "+
            "stop, use the /cancel command"
        )

    @staticmethod
    async def error_handler(update:Update, context: CallbackContext) -> None:
        """If there is an error, log it and let the user know something went wrong"""
        logging.error("An error occured: %s: %s", context.error, traceback.format_exc())

        if str(context.error) == "Login method is not known":
            await update.message.reply_text("Sorry, that login method has not been implemented yet, please choose one "+
                f"from the given list ({', '.join(LOGIN_METHODS)})")
            return
        
        if context.error.__str__()[:130] == 'Message: no such element: Unable to locate element: {"method":"css selector","selector":"button[data-test-id="bookable-slot-book-b':
            logger.info("User Allready registered for the course")
            await update.callback_query.edit_message_text("You seem to be allready registered for that course. Good Luck!")
            return

        if update.callback_query:
            await update.callback_query.edit_message_text(f"Sorry an error uccured. Please contact the Admins. Error={context.error.__str__()[:1000]}")
            return

        await update.message.reply_text(f"Sorry, an error occured. The error message reads: {context.error.__str__()[:1000]}")

    async def message_handler(self, update: Update, _: CallbackContext) -> None:
        """Check for updates"""
        telegram_id = update.effective_user.id
        key, s_choice = update.callback_query.data.split(',')
        choice = s_choice == 'Y'
        data = self.db.get_lesson_data_by_key(key)
        self.db.edit_data_point(key, "response", s_choice)

        if choice:
            user = self.db.get_user(telegram_id, query_key="telegram_id")
            usc = UscInterface(
                user['username'],
                user['password'],
                uva_login=user['login_method']=='uva'
            )
            usc.sign_up_for_lesson(data['sport'], data['datetime'])
            usc.close()

        text_choice = "Yes" if choice else "No"

        await update.callback_query.edit_message_text(
            update.callback_query.message.text +
            f"\n\nWe have recorded your choice as being {text_choice}. Good luck!"
        )

if __name__ == "__main__":
    load_dotenv()
    TelegramBot()
