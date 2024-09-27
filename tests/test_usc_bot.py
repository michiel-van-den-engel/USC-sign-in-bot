# pylint: disable=redefined-outer-name, protected-access
"""Define tests for the usc bot job in this module"""
from datetime import datetime as dt
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
from telegram.error import Forbidden

from usc_sign_in_bot.usc_bot import main


@pytest.fixture
def mock_usc():
    """Mock the usc object to return predefined lessons."""
    usc_mock = MagicMock()
    usc_mock.get_all_lessons.return_value = [
        {
            "time": dt.strptime("2024-09-17T18:00:00", "%Y-%m-%dT%H:%M:%S"),
            "trainer": "John Doe",
        },
        {
            "time": dt.strptime("2024-09-20T20:00:00", "%Y-%m-%dT%H:%M:%S"),
            "trainer": "Doe John",
        },
    ]
    return usc_mock


@pytest.fixture
def mock_application():
    """Mock the Telegram bot application."""
    app_mock = MagicMock()
    app_mock.bot.send_message = AsyncMock()
    return app_mock


@pytest.fixture
def mock_db():
    """Mock the database object (usc_db)."""
    db_mock = MagicMock()
    db_mock.get_all_users_in_sport.return_value = [
        {"user_id": 1, "telegram_id": 1001},
        {"user_id": 2, "telegram_id": 1002},
    ]
    db_mock.has_received_update.return_value = False
    db_mock.add_to_data.return_value = "key123"
    return db_mock


@pytest.mark.asyncio
async def test_send_messages(mock_application, mock_usc, mock_db):
    """Test that messages are sent to users."""
    await main(mock_application, mock_usc, mock_db)

    assert mock_application.bot.send_message.call_count == 4
    mock_application.bot.send_message.assert_called_with(
        1002,
        "There is a fencing lesson Friday at 20:00. The trainer is Doe John. Would you like to go?",
        reply_markup=ANY,
    )


@pytest.mark.asyncio
async def test_skip_if_received_update(mock_application, mock_usc, mock_db):
    """Test that messages are skipped if the user has already received updates."""
    # Set has_received_update to return True to simulate users who already received an update
    mock_db.has_received_update.return_value = True
    await main(mock_application, mock_usc, mock_db)

    mock_application.bot.send_message.assert_not_called()


@pytest.mark.asyncio
@patch("usc_sign_in_bot.usc_bot.logger.error")
async def test_handle_forbidden_error(mock_logger, mock_application, mock_usc, mock_db):
    """Test that Forbidden errors are logged and the process continues."""
    # Simulate a Forbidden error when trying to send a message
    mock_application.bot.send_message.side_effect = Forbidden("User blocked the bot")

    await main(mock_application, mock_usc, mock_db)
    assert mock_logger.call_count == 4
