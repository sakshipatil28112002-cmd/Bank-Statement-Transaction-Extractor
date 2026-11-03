import sqlite3

from fastapi import APIRouter, HTTPException

from database import create_connection
from schemas import UserCreate, UserUpdate


router = APIRouter(
    prefix="/profiles",
    tags=["User Profiles"]
)


# 1. Create a new user profile
@router.post("/")
def create_profile(user: UserCreate):

    try:
        with create_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO users (name, email, bank_name)
                VALUES (?, ?, ?)
                """,
                (user.name, user.email, user.bank_name)
            )

            conn.commit()

            return {
                "message": "Profile created successfully",
                "user_id": cursor.lastrowid
            }

    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )


# 2. Get all user profiles
@router.get("/")
def get_profiles():

    with create_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users"
        )

        rows = cursor.fetchall()

        return {"profiles": rows}


# 3. Get a profile by user ID
@router.get("/{user_id}")
def get_profile(user_id: int):

    with create_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        )

        user = cursor.fetchone()

        if user is None:
            raise HTTPException(
                status_code=404,
                detail="User profile not found"
            )

        return {"profile": user}


# 4. Update user profile
@router.put("/{user_id}")
def update_profile(user_id: int, user: UserUpdate):

    updates = user.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="No fields provided for update"
        )

    allowed_fields = {"name", "email", "bank_name"}

    if not set(updates).issubset(allowed_fields):
        raise HTTPException(
            status_code=400,
            detail="Invalid fields"
        )

    with create_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="User profile not found"
            )

        set_clause = ", ".join(
            f"{field} = ?" for field in updates
        )

        values = list(updates.values())
        values.append(user_id)

        try:
            cursor.execute(
                f"UPDATE users SET {set_clause} WHERE user_id = ?",
                values
            )

            conn.commit()

        except sqlite3.IntegrityError:
            raise HTTPException(
                status_code=400,
                detail="Email already exists"
            )

        return {
            "message": "Profile updated successfully"
        }


# 5. Delete user profile
@router.delete("/{user_id}")
def delete_profile(user_id: int):

    with create_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="User profile not found"
            )

        cursor.execute(
            """
            DELETE FROM transactions
            WHERE statement_id IN (
                SELECT statement_id
                FROM statements
                WHERE user_id = ?
            )
            """,
            (user_id,)
        )

        cursor.execute(
            "DELETE FROM statements WHERE user_id = ?",
            (user_id,)
        )

        cursor.execute(
            "DELETE FROM users WHERE user_id = ?",
            (user_id,)
        )

        conn.commit()

        return {
            "message": "Profile deleted successfully"
        }