"""Test module to test the Encryptor module in the src file"""

# pylint: disable=redefined-outer-name
import os
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from telegram import Update
from telegram.ext import ConversationHandler

from usc_sign_in_bot.telegram_bot import TelegramBot

LOGIN_METHOD, SPORT, USERNAME, PASSWORD, WRAP_UP = range(5)


@pytest.fixture
@patch("usc_sign_in_bot.telegram_bot.UscDataBase")
@patch("usc_sign_in_bot.telegram_bot.Application.builder")
def bot(mock_builder, mock_db):
    """Fixture for initializing the TelegramBot instance."""
    mock_token_builder = MagicMock(
        token=MagicMock(
            return_value=MagicMock(build=MagicMock(return_value=MagicMock()))
        )
    )
    mock_builder.return_value = mock_token_builder
    mock_db.return_value = MagicMock()

    bot = TelegramBot()
    return bot


@pytest.mark.asyncio
async def test_start(bot):
    """Test the start command."""
    update = AsyncMock(spec=Update)
    update.effective_user.id = 1234
    update.effective_user.mention_html.return_value = "user_1234"
    update.message.reply_html = AsyncMock()

    result = await bot.start(update, AsyncMock())

    update.message.reply_html.assert_called_once_with(
        "Heyhoy user_1234, Welcome in our service for USC sports. To start, I need some info from "
        + "you. What login method would you like to use? You can try (uva)"
    )
    assert result == LOGIN_METHOD


@pytest.mark.asyncio
@patch("usc_sign_in_bot.telegram_bot.UscDataBase")
async def test_ask_sports_valid_method(mock_database, bot):
    """Test the ask_sports method with a valid login method."""
    update = AsyncMock(spec=Update)
    update.message.text.strip.return_value = "uva"
    update.effective_user.id = 1234
    update.message.reply_html = AsyncMock()

    database_object = mock_database.return_value
    result = await bot.ask_sports(update, AsyncMock())

    database_object.insert_user.assert_called_once_with(1234, ANY, "uva")
    update.message.reply_html.assert_called_once_with(
        "Allright, we registered uva now we need to know the sport you want to participate in. "
        "Note that spelling (including captial letters) is very important here as this is where "
        "we will search for."
    )
    assert result == SPORT


@pytest.mark.asyncio
async def test_ask_sports_invalid_method(bot):
    """Test the ask_sports method with an invalid login method."""
    update = AsyncMock(spec=Update)
    update.message.text.strip.return_value = "invalid"
    update.effective_user.id = 1234

    with pytest.raises(ValueError, match="Login method is not known"):
        await bot.ask_sports(update, AsyncMock())


@pytest.mark.asyncio
@patch("usc_sign_in_bot.telegram_bot.UscDataBase")
async def test_ask_username(mock_database, bot):
    """Test the ask_username method."""
    update = AsyncMock(spec=Update)
    update.message.text = "Basketball"
    update.effective_user.id = 1234
    update.message.reply_html = AsyncMock()

    mock_db = mock_database.return_value

    result = await bot.ask_username(update, AsyncMock())

    mock_db.edit_data_point.assert_called_once_with(
        1234, "sport", "Basketball", table="users", key_column="telegram_id"
    )
    update.message.reply_html.assert_called_once_with(
        "Because the way this scraper work, we need to be able to log in on your behalf. If you "
        "don't feel confertable doing that, please type /cancel_setup. You should either way make "
        "sure that you don't use this password in more places. Now please type in your username "
        "that you use to log in. If you login with UVA, this will be your uva email adress."
    )
    assert result == USERNAME


@pytest.mark.asyncio
@patch("usc_sign_in_bot.telegram_bot.UscDataBase")
async def test_ask_password(mock_database, bot):
    """Test the telegram step asking for a password"""
    # Mock the update object to simulate a user message
    update = MagicMock()
    update.message.text = "test_username"  # Simulate the username entered
    update.effective_user.id = 123456  # Simulate the Telegram user ID

    # Mock the message reply_html method
    update.message.reply_html = AsyncMock()

    # Mock the database from builder
    mock_db = mock_database.return_value

    # Now call the function under test
    result = await bot.ask_password(update, MagicMock())

    # 1. Verify that database.edit_data_point is called correctly
    mock_db.edit_data_point.assert_called_once_with(
        123456,  # Telegram user ID
        "username",  # The field to update
        "test_username",  # The username that was entered
        table="users",
        key_column="telegram_id",
    )

    # 2. Verify that reply_html is called with the expected message
    update.message.reply_html.assert_called_once_with("and now type in the password:")

    # 3. Verify that the function returns PASSWORD
    assert result == PASSWORD


@pytest.mark.asyncio
@patch("usc_sign_in_bot.telegram_bot.Encryptor")
@patch("usc_sign_in_bot.telegram_bot.UscDataBase")
async def test_finish_sign_up(mock_db_builder, mock_encryptor, bot):
    """Test the function finishing the sign up process"""
    # Mock the update object to simulate a user message
    update = MagicMock()
    update.message.text = "test_password"  # Simulate user entering password
    update.effective_user.id = 123456  # Simulate the Telegram user ID

    # Set up the environment variable for encryption key
    os.environ["ENCRYPT_KEY"] = "test_key"

    # Create a mock for the Encryptor instance
    mock_encrypt_instance = mock_encryptor.return_value
    mock_encrypt_instance.encrypt_data.return_value = "encrypted_password"

    # Also create a mock for the database class
    mock_db = mock_db_builder.return_value

    # Mock the message reply_html method
    update.message.reply_html = AsyncMock()

    # Call the function under test
    result = await bot.finish_sign_up(update, MagicMock())

    # Assertions:
    # 1. Verify that Encryptor is initialized with the correct encryption key
    mock_encryptor.assert_called_once_with("test_key")

    # 2. Verify that encrypt_data is called with the correct password
    mock_encrypt_instance.encrypt_data.assert_called_once_with("test_password")

    # 3. Verify that database.edit_data_point is called with the correct arguments
    mock_db.edit_data_point.assert_called_once_with(
        123456,  # Telegram user ID
        "password",  # The field to update
        "encrypted_password",  # The encrypted password
        table="users",
        key_column="telegram_id",
    )

    # 4. Verify that reply_html is called with the correct message
    update.message.reply_html.assert_called_once_with(
        "You have finished the sign up process. Many love from us and we hope to see you in the "
        + "gym! &#10084;"
    )

    # 5. Verify that the function returns ConversationHandler.END
    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_cancel_setup(bot):
    """Test the function to cancel the setup process"""
    # Mock the update object
    update = MagicMock()
    update.effective_user.id = 123456  # Simulate Telegram user ID
    update.message.reply_text = MagicMock()

    # Call the cancel_setup method
    result = await bot.cancel_setup(update, MagicMock())

    # Assertions:
    # 1. Verify that the reply_text is called with the expected message
    update.message.reply_text.assert_called_once_with(
        "Canceled signup, Type /start to start over"
    )

    # 2. Verify that the method returns ConversationHandler.END
    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_help_command(bot):
    """Test the function that asks for help"""
    # Mock the update object
    update = MagicMock()
    update.message.reply_text = AsyncMock()

    # Call the help_command method
    result = await bot.help_command(update, MagicMock())

    # Assertions:
    # 1. Verify that reply_text is called with the expected message
    update.message.reply_text.assert_called_once_with(
        "We'll send you updates on all the trainings. You can sign up via the buttons. To stop, "
        + "use the /cancel command"
    )

    # 2. Verify that the function doesn't return anything
    assert result is None


@pytest.mark.asyncio
@patch("logging.error")
@patch("logging.info")
async def test_error_handler_login_method_error(mock_info, mock_error, bot):
    """Test the error handling of the telegram bot"""
    # Mock update and context
    update = MagicMock()
    context = MagicMock()
    context.error = "Login method is not known"
    update.message.reply_text = AsyncMock()

    # Call the error_handler function
    await bot.error_handler(update, context)

    # Assert logging for the error
    mock_error.assert_called_once_with(
        "An error occured: %s: %s", "Login method is not known", ANY
    )

    # Assert that the correct message is sent to the user
    update.message.reply_text.assert_called_once_with(
        "Sorry, that login method has not been implemented yet, please choose one from the given "
        + "list (uva)"
    )

    # Assert that logging.info was not called for other branches
    mock_info.assert_not_called()


@pytest.mark.asyncio
@patch("usc_sign_in_bot.telegram_bot.logger.info")
async def test_error_handler_already_registered(mock_info, bot):
    """Test the error for a user that has allready registered to a course"""
    # Mock update and context for registration error
    update = MagicMock()
    context = MagicMock()
    context.error.__str__.return_value = (
        "Message: no such element: Unable to locate element: "
        + '{"method":"css selector","selector":"button[data-test-id="bookable-slot-book-b'
    )
    update.callback_query.edit_message_text = AsyncMock()

    # Call the error_handler function
    await bot.error_handler(update, context)

    # Assert that logging for user already registered was called
    mock_info.assert_called_once_with("User Allready registered for the course")

    # Assert that the correct message is edited for the callback query
    update.callback_query.edit_message_text.assert_called_once_with(
        "You seem to be allready registered for that course. Good Luck!"
    )


@pytest.mark.asyncio
@patch("logging.error")
async def test_error_handler_callback_query(mock_error, bot):
    """Test the error handling for a general error callback"""
    # Mock update and context for a generic callback query error
    update = MagicMock()
    context = MagicMock()
    context.error.__str__.return_value = "Some random callback error"
    update.callback_query.edit_message_text = AsyncMock()

    # Call the error_handler function
    await bot.error_handler(update, context)

    # Assert that logging for the generic callback error was done
    mock_error.assert_called_once()

    print(update.call_args_list)
    # Assert that the correct message is edited for the callback query
    update.callback_query.edit_message_text.assert_called_once_with(
        "Sorry an error uccured. Please contact the Admins. Error=Some random callback error"
    )


@pytest.mark.asyncio
@patch("logging.error")
async def test_error_handler_generic_message_error(mock_error, bot):
    """Test another way a generic error might occur"""
    # Mock update and context for a generic message error
    update = MagicMock()
    context = MagicMock()
    context.error.__str__.return_value = "Some random error"
    update.callback_query = None
    update.message.reply_text = AsyncMock()

    # Call the error_handler function
    await bot.error_handler(update, context)

    # Assert that logging for the generic error was done
    mock_error.assert_called_once()

    # Assert that the correct message is sent to the user
    update.message.reply_text.assert_called_once_with(
        "Sorry, an error occured. The error message reads: Some random error"
    )


@pytest.mark.asyncio
@patch("usc_sign_in_bot.telegram_bot.UscInterface")
@patch("usc_sign_in_bot.telegram_bot.UscDataBase")
async def test_message_handler_yes_choice(mock_db_builder, mock_usc_interface, bot):
    """Check if hte app works corerctly when a user wants to sign up"""
    # Mock update and callback query
    update = MagicMock()
    update.effective_user.id = 123456  # Simulate Telegram user ID
    update.callback_query.data = "some_key,Y"
    update.callback_query.message.text = "Initial message"
    update.callback_query.edit_message_text = AsyncMock()

    # Mock the database
    mock_db = mock_db_builder.return_value

    # Mock database behavior
    mock_db.get_lesson_data_by_key = MagicMock(
        return_value={
            "sport": "Basketball",
            "datetime": "2024-09-30 10:00:00",
            "response": None,
        }
    )
    mock_db.get_user = MagicMock(
        return_value={
            "username": "user123",
            "password": "password",
            "login_method": "uva",
        }
    )
    mock_db.edit_data_point = MagicMock()

    # Mock the context manager behavior of UscInterface
    mock_usc = mock_usc_interface.return_value
    mock_usc.__enter__.return_value = mock_usc
    mock_usc.__exit__ = MagicMock()

    # Call the message_handler function
    await bot.message_handler(update, MagicMock())

    # Assertions:
    # 1. Ensure the database methods were called with correct arguments
    mock_db.get_lesson_data_by_key.assert_called_once_with("some_key")
    mock_db.edit_data_point.assert_called_once_with("some_key", "response", "Y")

    # 2. Ensure the UscInterface was initialized and used correctly
    mock_usc_interface.assert_called_once_with("user123", "password", uva_login=True)
    mock_usc.sign_up_for_lesson.assert_called_once_with(
        "Basketball", "2024-09-30 10:00:00"
    )

    # 3. Ensure the callback message was edited
    update.callback_query.edit_message_text.assert_called_once_with(
        "Initial message\n\nWe have recorded your choice as being Yes. Good luck!"
    )


@pytest.mark.asyncio
@patch("usc_sign_in_bot.telegram_bot.UscInterface")
@patch("usc_sign_in_bot.telegram_bot.UscDataBase")
async def test_message_handler_no_choice(mock_db_builder, mock_interface, bot):
    """Check if the app works correctly when a user chooses no"""
    # Mock update and callback query for 'No' choice
    update = MagicMock()
    update.effective_user.id = 123456  # Simulate Telegram user ID
    update.callback_query.data = "some_key,N"
    update.callback_query.message.text = "Initial message"
    update.callback_query.edit_message_text = AsyncMock()

    mock_interface.return_value = MagicMock()

    # Mock database behavior
    mock_db = mock_db_builder.return_value
    mock_db.get_lesson_data_by_key = MagicMock(
        return_value={
            "sport": "Basketball",
            "datetime": "2024-09-30 10:00:00",
            "response": None,
        }
    )
    mock_db.edit_data_point = MagicMock()

    # Call the message_handler function
    await bot.message_handler(update, MagicMock())

    # Assertions:
    # 1. Ensure the database methods were called with correct arguments
    mock_db.get_lesson_data_by_key.assert_called_once_with("some_key")
    mock_db.edit_data_point.assert_called_once_with("some_key", "response", "N")

    # 2. Ensure UscInterface was not called (since choice is 'No')
    # Check that UscInterface is not instantiated or used
    mock_interface.assert_not_called()

    # 3. Ensure the callback message was edited
    update.callback_query.edit_message_text.assert_called_once_with(
        "Initial message\n\nWe have recorded your choice as being No. Good luck!"
    )


@pytest.mark.asyncio
@patch("usc_sign_in_bot.telegram_bot.UscInterface")
@patch("usc_sign_in_bot.telegram_bot.UscDataBase")
async def test_message_handler_known_choice(mock_db_builder, mock_interface, bot):
    """Tests if it handles a message where the response is allready known"""
    # Mock update and callback query for 'No' choice
    update = MagicMock()
    update.effective_user.id = 123456  # Simulate Telegram user ID
    update.callback_query.data = "some_key,Y"

    # Mock database behavior
    mock_db = mock_db_builder.return_value
    mock_db.get_lesson_data_by_key = MagicMock(
        return_value={
            "sport": "Basketball",
            "datetime": "2024-09-30 10:00:00",
            "response": "Y",
        }
    )
    await bot.message_handler(update, MagicMock())

    mock_interface.assert_not_called()
    mock_db.edit_data_point.assert_not_called()
