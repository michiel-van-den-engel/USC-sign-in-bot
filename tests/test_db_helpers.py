"""Test module to test the db_helpers module in the src file"""
#pylint: disable=redefined-outer-name
from datetime import datetime
from unittest.mock import ANY, MagicMock, patch

import pytest
from psycopg2.errors import UniqueViolation

from usc_sign_in_bot.db_helpers import UscDataBase


@pytest.fixture
def mock_users():
    """Fixture for users stored in the db"""
    return [{"user_id": "user_id", "telegram_id": "telegram_id"}]


@pytest.fixture
def mock_db():
    """Fixture to create a mock database instance."""
    with patch("usc_sign_in_bot.db_helpers.psycopg2.connect") as mock_connect, patch(
        "usc_sign_in_bot.db_helpers.Encryptor"
    ) as mock_encryptor:

        # Mock the connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock the encryptor instance
        mock_encryptor_instance = mock_encryptor.return_value
        mock_encryptor_instance.generate_hash_key.return_value = "hashed_value"
        mock_encryptor_instance.decrypt_data.return_value = "decrypted_password"

        with UscDataBase(create_if_not_exists=False) as database:
            yield database

        # Cleanup (close the cursor and connection)
        mock_conn.close.assert_called_once()
        mock_cursor.close.assert_called_once()


def test_insert_user(mock_db):
    """Test inserting a new user into the database."""
    mock_db.cursor.execute = MagicMock()
    sign_up_time = datetime.now()

    # Call the method
    user_id = mock_db.insert_user("123456789", sign_up_time, "telegram")

    print(mock_db.cursor.execute.call_args_llist)
    # Assert that the insert query was executed
    mock_db.cursor.execute.assert_called_once_with(
        ANY, ("hashed_value", sign_up_time.isoformat(), "telegram", "123456789")
    )

    # Assert that the returned user_id is correct
    assert user_id == "hashed_value"


def test_insert_user_already_exists(mock_db):
    """Test handling of a user already existing in the database."""
    mock_db.cursor.execute = MagicMock(side_effect=UniqueViolation)
    mock_db.conn.rollback = MagicMock()

    sign_up_time = datetime.now()

    # Call the method (simulate user already exists)
    user_id = mock_db.insert_user("123456789", sign_up_time, "uva")

    # Assert that rollback was called after UniqueViolation
    mock_db.conn.rollback.assert_called_once()

    # Assert that the returned user_id is correct even on violation
    assert user_id == "hashed_value"


def test_add_to_data(mock_db):
    """Test adding a new record to the lessons table."""
    mock_db.cursor.execute = MagicMock()
    lesson_time = datetime.now()

    # Call the method
    lesson_key = mock_db.add_to_data(
        "Fencing", lesson_time, "user_123", True, trainer="John Doe"
    )

    # Assert that the insert query was executed with correct parameters
    mock_db.cursor.execute.assert_called_once_with(
        ANY,
        (
            "hashed_value",
            "user_123",
            str(lesson_time),
            "Fencing",
            "John Doe",
            True,
            None,
        ),
    )

    # Assert that the returned lesson key is correct
    assert lesson_key == "hashed_value"


def test_has_received_update(mock_db):
    """Test checking if a user has already received a message."""
    mock_db.cursor.execute = MagicMock()
    mock_db.cursor.fetchone = MagicMock(return_value=True)

    lesson_time = datetime.now()

    # Call the method
    result = mock_db.has_received_update("Fencing", lesson_time, "user_123")

    # Assert that the select query was executed with correct parameters
    mock_db.cursor.execute.assert_called_once_with(
        ANY, ("Fencing", str(lesson_time), True, "user_123")
    )

    # Assert that the result is True when a record is found
    assert result is True


def test_get_lesson_data_by_key(mock_db):
    """Test retrieving lesson data by its unique key."""
    mock_db.cursor.execute = MagicMock()
    mock_db.cursor.fetchone = MagicMock(
        return_value=(
            "lesson_123",
            "user_123",
            "2024-09-17T18:00:00",
            "Fencing",
            "John Doe",
            True,
            None,
        )
    )
    mock_db.cursor.description = [
        ("lesson_id",),
        ("user_id",),
        ("datetime",),
        ("sport",),
        ("trainer",),
        ("message_sent",),
        ("response",),
    ]

    # Call the method
    lesson_data = mock_db.get_lesson_data_by_key("lesson_123")

    # Assert that the select query was executed with correct parameters
    mock_db.cursor.execute.assert_called_once_with(ANY, ("lesson_123",))

    # Assert that the lesson data is returned correctly
    assert lesson_data["lesson_id"] == "lesson_123"
    assert lesson_data["sport"] == "Fencing"
    assert lesson_data["message_sent"] is True


def test_get_user_success(mock_db):
    """Test if the user is successfully retrieved with decrypted password."""
    # Mock the database cursor description and fetched result
    mock_db.cursor.description = [("user_id",), ("username",), ("password",)]
    mock_db.cursor.fetchone.return_value = (
        "user123",
        "test_user",
        "encrypted_password",
    )

    # Call the function
    result = mock_db.get_user("user123")

    # Check that the cursor was called with the correct query
    mock_db.cursor.execute.assert_called_once_with(ANY, ("user123",))

    # Check if the password was decrypted
    mock_db.encrypt.decrypt_data.assert_called_once_with("encrypted_password")

    # Check if the result is as expected
    expected_result = {
        "user_id": "user123",
        "username": "test_user",
        "password": "decrypted_password",
    }
    assert result == expected_result


def test_get_user_not_found(mock_db):
    """Test if a ValueError is raised when no user is found."""
    # Mock the case when no record is found
    mock_db.cursor.fetchone.return_value = None

    # Ensure ValueError is raised
    with pytest.raises(ValueError, match="User user123 not found"):
        mock_db.get_user("user123")

    # Ensure that the query was still executed
    mock_db.cursor.execute.assert_called_once_with(ANY, ("user123",))


def test_get_user_custom_query_key(mock_db):
    """Test if the function works with a custom query key."""
    # Mock the result
    mock_db.cursor.description = [("email",), ("username",), ("password",)]
    mock_db.cursor.fetchone.return_value = (
        "user@example.com",
        "test_user",
        "encrypted_password",
    )

    # Call the function with a custom query key
    result = mock_db.get_user("user@example.com", query_key="email")

    # Check that the cursor was called with the correct query and custom key
    mock_db.cursor.execute.assert_called_once_with(ANY, ("user@example.com",))

    # Check if the password was decrypted
    mock_db.encrypt.decrypt_data.assert_called_once_with("encrypted_password")

    # Check if the result is as expected
    expected_result = {
        "email": "user@example.com",
        "username": "test_user",
        "password": "decrypted_password",
    }
    assert result == expected_result


def test_edit_data_point_success(mock_db):
    """Test if your can edit the data point, check if commit is called and rollback is not called"""
    # Test successful execution of edit_data_point
    mock_db.edit_data_point("key_les", "col", "value", "table", "key_column")

    # Check that cursor.execute was called with the correct arguments
    mock_db.cursor.execute.assert_called_once_with(ANY, ("value", "key_les"))

    # Check that commit was called
    mock_db.conn.commit.assert_called_once()

    # Ensure rollback is not called if there are no errors
    mock_db.conn.rollback.assert_not_called()


def test_edit_data_point_error(mock_db):
    """Test if the rollback gets called properly when there is an error"""
    # Test that rollback is called on error
    mock_db.cursor.execute.side_effect = Exception("Database error")

    with pytest.raises(Exception):
        mock_db.edit_data_point("key_les", "col", "value", "table", "key_column")

    # Check that rollback was called
    mock_db.conn.rollback.assert_called_once()


def test_get_all_users_in_sport_success(mock_db: MagicMock, mock_users: list) -> None:
    """Test if you can sucessfully query all users"""
    # Test successful retrieval of users
    mock_db.cursor.fetchall.return_value = mock_users
    mock_db.cursor.description = [("user_id",), ("telegram_id",)]

    # Call the function
    result = mock_db.get_all_users_in_sport("sport")

    # Assert if it works
    assert result == mock_users
    mock_db.cursor.execute.assert_called_once_with(ANY, ("sport",))
    mock_db.conn.rollback.assert_not_called()
    mock_db.conn.rollback.assert_not_called()


def test_get_all_users_in_sport_error(mock_db: MagicMock):
    """Test if rollback get's called correctly when there is an error in geting all users"""
    # Test that rollback is called on error
    mock_db.cursor.execute.side_effect = Exception("Database error")

    with pytest.raises(Exception):
        mock_db.get_all_users_in_sport("sport")

    mock_db.conn.rollback.assert_called_once()
