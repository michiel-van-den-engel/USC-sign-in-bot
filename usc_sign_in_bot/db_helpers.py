"""In here, define functionsn to help with the sqlite tasks of the program"""

import logging
import os
import traceback
from asyncio import streams
from datetime import datetime as dt

import psycopg2
from psycopg2.errors import UniqueViolation

from usc_sign_in_bot.encryptor import Encryptor

logger = logging.getLogger(__name__)


def rollback_on_error(method):
    """Define wraper to rollback and log error in case of error in database connect function"""

    def wrapper(self, *args, **kwargs) -> any:
        try:
            return method(self, *args, **kwargs)

        except Exception as error:
            self.conn.rollback()
            logger.error("Error in %s: %s", method.__name__, traceback.format_exc())
            raise error

    return wrapper


class UscDataBase:
    """Make a connection to the USC database and hold functions to fix it"""

    def __init__(self, create_if_not_exists: bool = True):
        self.conn = psycopg2.connect(
            dbname=os.environ.get("POSTGRES_DB", "usc_db"),
            user=os.environ.get("POSTGRES_USER"),
            password=os.environ.get("POSTGRES_PASSWORD"),
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
        )
        self.cursor = self.conn.cursor()
        self.encrypt = Encryptor(os.environ.get("ENCRYPT_KEY"))

        # Don't continue checking if the database exists if it's not wanted
        if not create_if_not_exists:
            return

        with open("init.sql", "r", encoding="UTF-8") as file:
            init_query = file.read()

        self._multiple_query(init_query)

    def __enter__(self):
        # return the object when entering the context
        return self

    def __exit__(self, _, __, ___):
        # Ensure cursor is closed when exiting the context
        if self.cursor:
            self.cursor.close()

        # Ensure connection is closed when exiting the context
        if self.conn:
            self.conn.close()

    def _multiple_query(self, query: str) -> None:
        """Execute a query with multiple statements"""
        # Execute some scripts to make sure the table is in there
        for command in query.split(";"):
            # Don't execute empty lines
            if command.strip():
                self.cursor.execute(command)

        self.conn.commit()

    @rollback_on_error
    def insert_user(
        self, telegram_id: str, sign_up_time: dt, login_method: str
    ) -> None:
        """
        Insert a new user into the database with a unique user ID.

        This function generates a unique user ID by hashing the provided `telegram_id`.
        It then inserts the user's information, including the sign-up time and login
        method, into the `users` table. The `user_id` is used instead of the `telegram_id`
        for potential security reasons, ensuring that sensitive data like `telegram_id`
        is not exposed in messages or other operations.

        Parameters
        ----------
        telegram_id : str
            The Telegram ID of the user. This will be hashed to create a unique user ID.

        sign_up_time : datetime.datetime
            The date and time when the user signed up. This should be a `datetime` object.

        login_method : str
            The method used by the user to log in, such as "uva".

        Returns
        -------
        str
            The unique `user_id` generated for the user.
        """
        # Create the user idea as a hash of the telegram ID, we could of course use the telegram
        # id, but because we might want to use the user_id for sending it away later on we don't
        # want to send the telegram_id in the message to everyone
        user_id = self.encrypt.generate_hash_key(str(telegram_id))

        try:
            self.cursor.execute(
                """
                INSERT INTO users (user_id, sign_up_date, login_method, telegram_id)
                VALUES (%s, %s, %s, %s)
            """,
                (user_id, sign_up_time.isoformat(), login_method, telegram_id),
            )

            # Commit the changes to the database
            self.conn.commit()

            return user_id

        # If the user allready exists, return the user_id
        except UniqueViolation:
            logger.warning("User %s allready exists.", user_id)
            self.conn.rollback()
            return user_id

    @rollback_on_error
    def add_to_data(
        self,
        sport: str,
        daytime: dt,
        user_id: str,
        message_sent: bool,
        response: str = None,
        trainer: str = None,
    ) -> str:
        """
        Adds a new record to the `lessons` table in the database.

        This function generates a unique hash key based on the sport and datetime,  and inserts
        these values along with other details into the `lessons` table. The function commits the
        changes to the database and returns the generated key.

        Parameters
        ----------
        sport : str
            The name of the sport (e.g., "Basketball").
        daytime : datetime
            The date and time of the lesson. This is used to generate a unique key and to
            format the `time` and `day`.
        message_sent : bool
            A flag indicating whether a message has been sent (True) or not (False).
        response : str, optional
            An optional response string related to the lesson. Default is None.
        trainer : str, optional
            The name of the trainer. Default is None.

        Returns
        -------
        str
            The unique key generated for the lesson record, which is used as the primary key in the
            database.

        Raises
        ------
        sqlite3.DatabaseError
            If there is an issue with the database operation (e.g., if the database connection is
            not established or the SQL query fails).
        """
        # Generate a hash key based on sport and datetime. This combination should be unique. This
        # is done such that we don't have any key colissions as well as unsafe indenting keys
        key = self.encrypt.generate_hash_key(f"{sport}{daytime.isoformat()}{user_id}")

        # Execute query to insert the values into the database
        self.cursor.execute(
            """
            INSERT INTO lessons (lesson_id, user_id, datetime, sport, trainer, message_sent,
                response)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
            (key, user_id, str(daytime), sport, trainer, message_sent, response),
        )

        # Commit the changes to the database
        self.conn.commit()

        # Return the generated key sush that it can be used in the program for querying the record
        # later on
        return key

    @rollback_on_error
    def has_received_update(self, sport: str, daytime: dt, user_id: str) -> bool:
        """
        Check if the specified sport and datetime combination has already received an email.

        This function queries the `lessons` table in the database to determine if a record with the
        given sport and datetime exists and indicates that an email has been sent (i.e.,
        `message_sent` is True).

        Parameters
        ----------
        sport : str
            The name of the sport to check (e.g., "Basketball").
        daytime : datetime.datetime
            The date and time of the lesson to check. This is used to match records in the database

        Returns
        -------
        bool
            Returns True if a record with the given sport and datetime exists and `message_sent` is
            True, otherwise returns False.
        """
        # Start with querying all the records with the sport, datetime and a message sent
        self.cursor.execute(
            """
            SELECT lesson_id FROM lessons
            WHERE sport = %s AND datetime = %s AND message_sent = %s AND user_id = %s
        """,
            (sport, str(daytime), True, user_id),
        )

        # Then get the first result of the query
        result = self.cursor.fetchone()

        # Cast it to a bool, as when the result is [] it will result in False, while returning True
        # if the result is filled
        return bool(result)

    @rollback_on_error
    def get_lesson_data_by_key(self, key_les) -> list[str, int, bool]:
        """
        Retrieve lesson data from the database by lesson ID.

        This function queries the `lessons` table using a unique lesson ID (`lesson_id`). It
        retrieves the corresponding record, converts the data to appropriate types, and returns it
        as a list. The unique lesson ID ensures that only one record is returned.

        Parameters
        ----------
        key_les : str
            The unique identifier for the lesson. This should match the `lesson_id` column in the
            database.

        Returns
        -------
        list
            A list containing the lesson data. The list includes:
            - `lesson_id` (str): The unique identifier of the lesson.
            - `datetime` (datetime.datetime): The date and time of the lesson.
            - `message_sent` (bool): A flag indicating whether a message was sent for this lesson.
            - Additional fields from the `lessons` table, depending on the schema.

        Raises
        ------
        sqlite3.OperationalError
            If there is an issue with executing the SQL query or if the table does not exist.
        TypeError
            If there is a type conversion error while processing the `datetime` or `message_sent`
            fields.
        """
        # Start with querying the records we want to by key
        self.cursor.execute(
            """
            SELECT * FROM lessons
            WHERE lesson_id = %s
        """,
            (key_les,),
        )

        # Because the key should be unique, there should only be one record. So take that one
        result = self.cursor.fetchone()

        # Create a dictionary for the result for easy handling
        cols = [desc[0] for desc in self.cursor.description]
        dict_result = dict(zip(cols, result))

        # Edit some types to the correct type
        dict_result["datetime"] = dict_result["datetime"]
        dict_result["message_sent"] = bool(dict_result["message_sent"])

        return dict_result

    @rollback_on_error
    def get_user(self, unit_id: str, query_key: streams = "user_id") -> dict[str, object]:
        """
        Retrieve a user's information from the database based on a specified query key.

        This function queries the `users` table to fetch all columns for a user whose
        column specified by `query_key` matches the provided `id`. The result is returned
        as a dictionary where the keys are the column names and the values are the respective
        data from the row. The user's password is decrypted before returning.

        Parameters
        ----------
        unit_id : str
            The value to search for in the specified column (`query_key`). This can be a
            user ID, email, username, or any other unique identifier.

        query_key : str, optional
            The column name to search by in the `users` table (default is `"user_id"`).

        Returns
        -------
        dict[str, object]
            A dictionary containing the user's information with column names as keys.
            The `password` field is decrypted before returning.

        Raises
        ------
        ValueError
            If no record is found in the database that matches the query.
        """
        # Start with querying the records we want
        self.cursor.execute(
            f"""
            SELECT * FROM users
            WHERE {query_key} = %s;
        """,
            (unit_id,),
        )

        # Because the key should be unique, there should only be one record. So take that one
        result = self.cursor.fetchone()

        # If result is none, return an error as it's not unique
        if not result:
            raise ValueError(f"User {unit_id} not found")

        # Create a dictionary for the result for easy handling
        cols = [desc[0] for desc in self.cursor.description]
        result_dict = dict(zip(cols, result))

        # Decrypt the password
        result_dict["password"] = self.encrypt.decrypt_data(result_dict["password"])

        # Return the result
        return result_dict

    @rollback_on_error
    def edit_data_point(
        self,
        key_les: str,
        col: str,
        value: str,
        table: str = "lessons",
        key_column="lesson_id"
    ) -> None:
        """
        Update a specific column of a lesson record in the database.

        This function updates a single column of a record in the `lessons` table identified by a
        unique lesson ID (`lesson_id`). It sets the specified column to the given value and commits
        the changes to the database.

        Parameters
        ----------
        key_les : str
            The unique identifier of the lesson record to be updated.
        col : str
            The name of the column to be updated. This should be a valid column name in the
            `lessons` table.
        value : str
            The new value to set for the specified column. This should be a string representation
            of the value.

        Returns
        -------
        None
            This function does not return a value. It performs an update operation on the database.

        Raises
        ------
        sqlite3.OperationalError
            If there is an issue with executing the SQL query or if the column name is invalid.
        """
        # Execute the update statement
        self.cursor.execute(
            f"""
            UPDATE {table}
            SET {col} = %s
            WHERE {key_column} = %s;
        """,
            (value, key_les),
        )

        # Commit the changes to the database
        self.conn.commit()

    @rollback_on_error
    def get_all_users_in_sport(self, sport: str) -> list[dict[str, str]]:
        """
        Retrieve a list of all users participating in a specific sport.

        This function executes a SQL query to fetch all user IDs and Telegram IDs of users
        who are associated with the given sport. The results are returned as a list of
        dictionaries, where each dictionary represents a row in the result set and
        contains column names as keys.

        Parameters
        ----------
        sport : str
            The name of the sport for which the users are to be retrieved.

        Returns
        -------
        list of dict[str, any]
            A list of dictionaries, where each dictionary contains the columns `user_id`
            and `telegram_id` for a user. Each key in the dictionary corresponds to a column
            name, and the values correspond to the respective values in the row.
        """
        # Execute the query to get all the users in the sport
        self.cursor.execute(
            """
            SELECT user_id, telegram_id
            FROM users
            WHERE sport = %s;
        """,
            (sport,),
        )

        # Fetch all the rows that are selected
        rows = self.cursor.fetchall()

        # Make sure the result is a list of dictionaries
        cols = [desc[0] for desc in self.cursor.description]
        result = [dict(zip(cols, row)) for row in rows]

        return result
