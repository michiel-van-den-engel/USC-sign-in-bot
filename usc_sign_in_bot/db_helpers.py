"""In here, define functionsn to help with the sqlite tasks of the program"""
from asyncio import streams
import os
import psycopg2
from psycopg2.errors import UniqueViolation, Error
from psycopg2 import sql
import hashlib
import logging
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from base64 import b64decode, b64encode

from datetime import datetime as dt

logger = logging.getLogger(__name__)

def _generate_hash_key(hash_str:str) -> str:
    """Create a hashed key based on sport and datetime"""
    # Create a SHA_256 hash for the combined string
    hash_object = hashlib.sha256(hash_str.encode())

    # Return the hexadecimal string of the hash. Only get the first 60 characters as the
    # fuckers at telegrem does not support longer than 64 characters and we need to add some
    # other info as well
    return hash_object.hexdigest()[:60]

def _get_key() -> str:
    key = os.environ.get("ENCRYPT_KEY")

    return key.ljust(32)[:32].encode('utf-8')

def encrypt_data(text_to_be_encripted:str) -> str:

    # Get the encription key from the environment
    key = _get_key()

    # Use the cipher with AES algorithm in CBC mode and add a random IV
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()

    # pad the plaintext such that it becomes a multiple of the wanted block size
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(text_to_be_encripted.encode('utf-8')) + padder.finalize()

    # Encrypt the padded data
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()

    # Return the IV and the ciphertext, for easy storage
    return b64encode(iv + ciphertext).decode('utf-8')

def decrypt_data(encrypted_data:str) -> str:

    # Get the encription key from the environment
    key = _get_key()

    # Decode the base64-encoded text
    ciphertext = b64decode(encrypted_data)

    # split the data in the random string and the actual encrypted text
    iv, actual_ciphertext = ciphertext[:16], ciphertext[16:]

    # Now create the right decryptor objects to decrypt the text
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()

    # Decrypt the actual decrypted text
    padded_plaintext = decryptor.update(actual_ciphertext) + decryptor.finalize()

    # Now unpadd the text
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()

    return plaintext.decode('utf-8')

class db():

    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=os.environ.get("POSTGRES_DB", "usc_db"),
            user=os.environ.get("POSTGRES_USER"),
            password=os.environ.get("POSTGRES_PASSWORD"),
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=os.environ.get("POSTGRES_PORT", '5432')
        )
        self.cursor = self.conn.cursor()

        """Initiate the db and make sure the tables alle exist"""
        with open("init.sql", 'r', encoding="UTF-8") as file:
            init_query = file.read()

        self._multiple_query(init_query)

    def _multiple_query(self, query:str) -> None:
        """Execute a query with multiple statements"""
        # Execute some scripts to make sure the table is in there
        for command in query.split(';'):
            # Don't execute empty lines
            if command.strip():
                self.cursor.execute(command)

        self.conn.commit()

    def insert_user(self, telegram_id:str, sign_up_time:dt, login_method:str) -> None:
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
            The method used by the user to log in, such as "telegram", "google", or "email".

        Returns
        -------
        str
            The unique `user_id` generated for the user.
        """
        # Create the user idea as a hash of the telegram ID, we could of course use the telegram id, but
        # because we might want to use the user_id for sending it away later on we don't want to send
        # the telegram_id in the message to everyone
        user_id = _generate_hash_key(str(telegram_id))

        try:
            self.cursor.execute("""
                INSERT INTO users (user_id, sign_up_date, login_method, telegram_id)
                VALUES (%s, %s, %s, %s)
            """, (user_id, sign_up_time.isoformat(), login_method, telegram_id))

            # Commit the changes to the database
            self.conn.commit()

            return user_id

        # If the user allready exists, return the user_id
        except UniqueViolation:
            logger.warning("User %s allready exists.", user_id)
            self.conn.rollback()
            return user_id

    def add_to_data(self, sport:str, daytime: dt, user_id:str, message_sent:bool, response:str=None, trainer:str=None) -> str:
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
            The unique key generated for the lesson record, which is used as the primary key in the database.

        Raises
        ------
        sqlite3.DatabaseError
            If there is an issue with the database operation (e.g., if the database connection is not
            established or the SQL query fails).
        """
        # Generate a hash key based on sport and datetime. This combination should be unique. This is
        # done such that we don't have any key colissions as well as unsafe indenting keys
        key = _generate_hash_key(f"{sport}{daytime.isoformat()}{user_id}")

        try:
            # Execute query to insert the values into the database
            self.cursor.execute("""
                INSERT INTO lessons (lesson_id, user_id, datetime, sport, trainer, message_sent, response)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (key, user_id, str(daytime), sport, trainer, message_sent, response))

            # Commit the changes to the database
            self.conn.commit()

            # Return the generated key sush that it can be used in the program for querying the record later on
            return key

        except Error as e:
            self.conn.rollback()
            raise e

    def has_received_update(self, sport:str, daytime:dt, user_id:str) -> bool:
        """
        Check if the specified sport and datetime combination has already received an email.

        This function queries the `lessons` table in the database to determine if a record with the given
        sport and datetime exists and indicates that an email has been sent (i.e., `message_sent` is True).

        Parameters
        ----------
        sport : str
            The name of the sport to check (e.g., "Basketball").
        daytime : datetime.datetime
            The date and time of the lesson to check. This is used to match records in the database.

        Returns
        -------
        bool
            Returns True if a record with the given sport and datetime exists and `message_sent` is True,
            otherwise returns False.
        """
        # Start with querying all the records with the sport, datetime and a message sent
        self.cursor.execute("""
            SELECT lesson_id FROM lessons
            WHERE sport = %s AND datetime = %s AND message_sent = %s AND user_id = %s
        """, (sport, str(daytime), True, user_id))

        # Then get the first result of the query
        result = self.cursor.fetchone()

        # Cast it to a bool, as when the result is [] it will result in False, while returning True if the
        # result is filled
        return bool(result)

    def get_lesson_data_by_key(self, key_les) -> list[str, int, bool]:
        """
        Retrieve lesson data from the database by lesson ID.

        This function queries the `lessons` table using a unique lesson ID (`lesson_id`). It retrieves the 
        corresponding record, converts the data to appropriate types, and returns it as a list. The unique 
        lesson ID ensures that only one record is returned.

        Parameters
        ----------
        key_les : str
            The unique identifier for the lesson. This should match the `lesson_id` column in the database.

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
            If there is a type conversion error while processing the `datetime` or `message_sent` fields.
        """
        # Start with querying the records we want to by key
        self.cursor.execute("""
            SELECT * FROM lessons
            WHERE lesson_id = %s
        """, (key_les,))

        # Because the key should be unique, there should only be one record. So take that one
        result = self.cursor.fetchone()

        # Create a dictionary for the result for easy handling
        cols = [desc[0] for desc in self.cursor.description]
        dict_result = dict(zip(cols, result))

        # Edit some types to the correct type
        dict_result['datetime'] = dict_result['datetime']
        dict_result['message_sent'] = bool(dict_result['message_sent'])

        return dict_result

    def get_user(self, id:str, query_key:streams="user_id") -> dict[str, object]:
        """
        Retrieve a user's information from the database based on a specified query key.

        This function queries the `users` table to fetch all columns for a user whose 
        column specified by `query_key` matches the provided `id`. The result is returned 
        as a dictionary where the keys are the column names and the values are the respective 
        data from the row. The user's password is decrypted before returning.

        Parameters
        ----------
        id : str
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
        self.cursor.execute(f"""
            SELECT * FROM users
            WHERE {query_key} = %s;
        """, (id,))

        # Because the key should be unique, there should only be one record. So take that one
        result = self.cursor.fetchone()

        # Create a dictionary for the result for easy handling
        cols = [desc[0] for desc in self.cursor.description]
        result_dict = dict(zip(cols, result))

        # Decrypt the password
        result_dict['password'] = decrypt_data(result_dict['password'])

        # Return the result
        return result_dict

    def edit_data_point(self, key_les:str, col:str, value:str, table:str="lessons", key_column="lesson_id") -> None:
        """
        Update a specific column of a lesson record in the database.

        This function updates a single column of a record in the `lessons` table identified by a unique 
        lesson ID (`lesson_id`). It sets the specified column to the given value and commits the changes 
        to the database.

        Parameters
        ----------
        key_les : str
            The unique identifier of the lesson record to be updated.
        col : str
            The name of the column to be updated. This should be a valid column name in the `lessons` table.
        value : str
            The new value to set for the specified column. This should be a string representation of the value.

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
        self.cursor.execute(f"""
            UPDATE {table}
            SET {col} = %s
            WHERE {key_column} = %s;
        """, (value, key_les))

        # Commit the changes to the database
        self.conn.commit()

    def get_all_users_in_sport(self, sport:str) -> list[dict[str, str]]:
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
        self.cursor.execute("""
            SELECT user_id, telegram_id
            FROM users
            WHERE sport = %s;
        """, (sport, ))

        # Fetch all the rows that are selected
        rows = self.cursor.fetchall()

        # Make sure the result is a list of dictionaries
        cols = [desc[0] for desc in self.cursor.description]
        result = [dict(zip(cols, row)) for row in rows]

        return result

