from logging import Filter
import os
import asyncio
import logging
from itertools import product

import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, CallbackQueryHandler, CallbackContext
from dotenv import load_dotenv

from usc_interface import USC_Interface
from db_helpers import add_to_data, has_received_update, get_all_users_in_sport

load_dotenv()

SPORT = 'Schermen'

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Create the application and pass your bot's token
application = Application.builder().token(os.environ['BOTTOKEN']).build()
usc = USC_Interface(
    os.environ['UVA_USERNAME'],
    os.environ['UVA_PASSWORD'],
    uva_login=True
)


async def main() -> None:
    lessons = usc.get_all_lessons("Schermen")
    all_sport_users = get_all_users_in_sport(SPORT)

    tasks = []
    for les, user in product(lessons, all_sport_users):
        # Skip the sending of the message if the user has allready had a response
        if has_received_update(SPORT, les['time'], user['user_id']):
            continue

        # Create a unique key to give to 
        key_les = add_to_data(SPORT, les['time'], user['user_id'], True, trainer=les['trainer'])

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes", callback_data=key_les+",Y")],
            [InlineKeyboardButton("No",  callback_data=key_les+",N")]
        ])
        tasks.append(asyncio.create_task(application.bot.send_message(os.environ['TELEGRAM_USER_ID'],
            f"There is a fencing lesson {les['time'].strftime('%A')} at {les['time'].strftime('%H:%M')}. "+
            f"The trainer is {les['trainer']}. Would you like to go?",
            reply_markup=markup
        )))

        logger.info("Ask for lesson %s and %s", les['time'].isoformat(), SPORT)
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
