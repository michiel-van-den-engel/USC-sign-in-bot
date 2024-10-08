"""Module for calling the job checking for new lessons"""

import asyncio
import logging
import os
from itertools import product

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden
from telegram.ext import Application

from usc_sign_in_bot.db_helpers import UscDataBase
from usc_sign_in_bot.usc_interface import UscInterface

load_dotenv()

SPORT = "Schermen"

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.INFO)

logger = logging.getLogger(__name__)


async def main(
    application: Application, usc: UscInterface, usc_db: UscDataBase
) -> None:
    """Main function of the module, calling this will start the job"""
    lessons = usc.get_all_lessons("Schermen")
    all_sport_users = usc_db.get_all_users_in_sport(SPORT)

    tasks = []
    for les, user in product(lessons, all_sport_users):
        # Skip the sending of the message if the user has allready had a response
        if usc_db.has_received_update(SPORT, les["time"], user["user_id"]):
            continue

        # Create a unique key to give to
        key_les = usc_db.add_to_data(
            SPORT, les["time"], user["user_id"], True, trainer=les["trainer"]
        )

        # Create the buttons for the user to press
        markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Yes", callback_data=key_les + ",Y")],
                [InlineKeyboardButton("No", callback_data=key_les + ",N")],
            ]
        )
        try:
            tasks.append(
                asyncio.create_task(
                    application.bot.send_message(
                        user["telegram_id"],
                        f"There is a fencing lesson {les['time'].strftime('%A')} at "
                        + les["time"].strftime("%H:%M")
                        + f". The trainer is {les['trainer']}. Would you like to go?",
                        reply_markup=markup,
                    )
                )
            )

            logger.info("Ask for lesson %s and %s", les["time"].isoformat(), SPORT)
            await asyncio.gather(*tasks)

        # If the action is not allowed, log it but continue with other users
        except Forbidden as error:
            logger.error(
                "Forbidden for user %s, with error message: %s", user["user_id"], error
            )


def start_bot_job():
    """Start the bot and interface neeeded for the fnction, then calll the main"""
    # Create the application and pass your bot's token
    application = Application.builder().token(os.environ["BOTTOKEN"]).build()
    with UscInterface(
        os.environ["UVA_USERNAME"], os.environ["UVA_PASSWORD"], uva_login=True
    ) as usc:

        usc_db = UscDataBase()

        asyncio.run(main(application, usc, usc_db))
