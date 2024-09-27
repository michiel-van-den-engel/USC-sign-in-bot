"""Main of the module, mainly used to point to the right script"""
import sys

from usc_sign_in_bot.telegram_bot import TelegramBot
from usc_sign_in_bot.usc_bot import start_bot_job


def main() -> None:
    """main function for this script, points into the right direction for the givenmode"""
    if len(sys.argv) != 2:
        raise ValueError("Please give a valid mode, bot or job")

    if sys.argv[1] not in ("bot", "job"):
        raise ValueError("Unknown input")

    if sys.argv[1] == "bot":
        TelegramBot()

    elif sys.argv[1] == "job":
        start_bot_job()


if __name__ == "__main__":
    main()
