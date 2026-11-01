import sqlite3

DB_NAME = "bank_statement.db"


def create_connection():
    """Create and return a SQLite database connection with timeout, foreign keys, and WAL mode."""
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def create_tables():
    """Create all required tables for users, statements, and transactions."""
    with create_connection() as conn:
        cursor = conn.cursor()

        # 1. Users Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            bank_name TEXT NOT NULL
        )
        """)

        # 2. Statements Table
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

        # 3. Transactions Table
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

        conn.commit()


def update_user_profile(user_id, name, bank_name):
    """Update profile details for an existing user."""
    with create_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET name = ?, bank_name = ?
            WHERE user_id = ?
            """,
            (name, bank_name, user_id),
        )
        conn.commit()


def delete_user_profile(user_id):
    """Delete a user profile and clean up all dependent statements and transactions."""
    with create_connection() as conn:
        cursor = conn.cursor()

        # Explicitly remove child transactions first
        cursor.execute(
            """
            DELETE FROM transactions 
            WHERE statement_id IN (
                SELECT statement_id FROM statements WHERE user_id = ?
            )
            """,
            (user_id,),
        )

        # Explicitly remove child statements
        cursor.execute("DELETE FROM statements WHERE user_id = ?", (user_id,))

        # Delete the user record
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))

        conn.commit()