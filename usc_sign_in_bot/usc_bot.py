from logging import Filter
import os
import asyncio

import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, CallbackQueryHandler, CallbackContext
from dotenv import load_dotenv

from usc_interface import USC_Interface

load_dotenv()

SPORT = 'Schermen'

# Create the application and pass your bot's token
application = Application.builder().token(os.environ['BOTTOKEN']).build()
usc = USC_Interface(
    os.environ['UVA_USERNAME'],
    os.environ['UVA_PASSWORD'],
    uva_login=True
)
    

async def main() -> None:
    lessons = usc.get_all_lessons("Schermen")

    tasks = []
    for les in lessons:
        leskey = SPORT + ',' + les['time'].strftime('%Y-%m-%dT%H:%M')

        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes", callback_data=leskey)],
            [InlineKeyboardButton("No",  callback_data=leskey)]
        ])
        tasks.append(asyncio.create_task(application.bot.send_message(os.environ['TELEGRAM_USER_ID'],
            f"There is a fencing lesson {les['time'].strftime('%A')} at {les['time'].strftime('%H:%M')}."+
            f"The trainer is {les['trainer']}. Would you like to go?",
            reply_markup=markup
        )))

        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())