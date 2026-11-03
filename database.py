import sqlite3

# Name of the SQLite database file
DB_NAME = "bank_statement.db"


# Create a connection with the database
def create_connection():

    # Connect to SQLite database with 30 seconds timeout
    conn = sqlite3.connect(DB_NAME, timeout=30.0)

    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON")

    # Enable Write-Ahead Logging for better database access
    conn.execute("PRAGMA journal_mode = WAL")

    # Return the database connection
    return conn


# Create all required database tables
def create_tables():

    # Open database connection
    with create_connection() as conn:
        cursor = conn.cursor()

        # 1. Create Users Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            bank_name TEXT NOT NULL
        )
        """)

        # 2. Create Statements Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS statements (
            statement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            upload_date TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            UNIQUE (user_id, file_hash)
        )
        """)

        # 3. Create Transactions Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            statement_id INTEGER NOT NULL,
            transaction_ref TEXT,
            amount REAL NOT NULL,
            transaction_type TEXT NOT NULL,
            transaction_date TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (statement_id) REFERENCES statements(statement_id) ON DELETE CASCADE
        )
        """)

        # Save all table creation changes
        conn.commit()


# Update an existing user's profile
def update_user_profile(user_id, name, bank_name):

    # Open database connection
    with create_connection() as conn:
        cursor = conn.cursor()

        # Update name and bank name using user ID
        cursor.execute(
            """
            UPDATE users
            SET name = ?, bank_name = ?
            WHERE user_id = ?
            """,
            (name, bank_name, user_id),
        )

        # Save updated profile details
        conn.commit()


# Delete a user profile and its related records
def delete_user_profile(user_id):

    # Open database connection
    with create_connection() as conn:
        cursor = conn.cursor()

        # First, delete transactions linked to the user's statements
        cursor.execute(
            """
            DELETE FROM transactions 
            WHERE statement_id IN (
                SELECT statement_id FROM statements WHERE user_id = ?
            )
            """,
            (user_id,),
        )

        # Delete all statements belonging to the user
        cursor.execute(
            "DELETE FROM statements WHERE user_id = ?",
            (user_id,)
        )

        # Finally, delete the user profile
        cursor.execute(
            "DELETE FROM users WHERE user_id = ?",
            (user_id,)
        )

        # Save all deletion changes
        conn.commit()