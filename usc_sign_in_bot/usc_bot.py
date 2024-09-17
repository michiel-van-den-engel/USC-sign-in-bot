import os
import asyncio
import logging
from itertools import product

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application
from telegram.error import Forbidden

from dotenv import load_dotenv

from .usc_interface import USC_Interface
from .db_helpers import db

load_dotenv()

SPORT = 'Schermen'

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.INFO)

logger = logging.getLogger(__name__)



async def main(application:Application, usc:USC_Interface, usc_db:db) -> None:
    lessons = usc.get_all_lessons("Schermen")
    all_sport_users = usc_db.get_all_users_in_sport(SPORT)

    tasks = []
    print("Lessons and users", lessons, all_sport_users)
    for les, user in product(lessons, all_sport_users):
        # Skip the sending of the message if the user has allready had a response
        if usc_db.has_received_update(SPORT, les['time'], user['user_id']):
            continue

        # Create a unique key to give to 
        key_les = usc_db.add_to_data(SPORT, les['time'], user['user_id'], True, trainer=les['trainer'])

        # Create the buttons for the user to press
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes", callback_data=key_les+",Y")],
            [InlineKeyboardButton("No",  callback_data=key_les+",N")]
        ])
        try:
            tasks.append(asyncio.create_task(application.bot.send_message(user['telegram_id'],
                f"There is a fencing lesson {les['time'].strftime('%A')} at {les['time'].strftime('%H:%M')}. "+
                f"The trainer is {les['trainer']}. Would you like to go?",
                reply_markup=markup
            )))

            logger.info("Ask for lesson %s and %s", les['time'].isoformat(), SPORT)
            await asyncio.gather(*tasks)
        
        # If the action is not allowed, log it but continue with other users
        except Forbidden as e:
            logger.error("Forbidden for user %s, with error message: %s", user['user_id'], e)

if __name__ == "__main__":
    # Create the application and pass your bot's token
    application = Application.builder().token(os.environ['BOTTOKEN']).build()
    usc = USC_Interface(
        os.environ['UVA_USERNAME'],
        os.environ['UVA_PASSWORD'],
        uva_login=True
    )

    usc_db = db()

    try:
        asyncio.run(main(application, usc, usc_db))
    finally:
        usc.quit()
