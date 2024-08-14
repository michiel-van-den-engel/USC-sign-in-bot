# USC sign in Bot

The bot is programmed in Python. To manage the environment Pipenv is used. If you want to setup a pipenv environment please use the command ```pipenv sync``` to make sure the pipenv environment is up to date.

The program is devided in two parts. The Telegram bot which needs to run continuously to listen for responses in telegram. It can be run by running the command:
```
pipenv run python usc_sign_in_bot/telegram_bot.py
```

There is also the job that can check for unsent updates for new lessons in the next 7 days. It is best to run this in a cronjob every day.
To run the job you can run the following command in your crontab.
```
pipenv run python usc_sign_in_bot/usc_bot.py
```

Have fun and you are welcome to contribute!

## Limitations/possible future improvements
* for now, only uva login is supported
* Only Fencing as a sport is supported in the usc_bot file, in the telegram bot you can have multiple sports
* Multiple sports cannot be saved. Should be made into a list
