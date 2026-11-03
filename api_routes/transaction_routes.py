#We will write APIs for:

#View transaction history.
#Search transactions.
#Filter transactions.
#Calculate debit and credit totals.
#export transactions.

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from database import create_connection

router = APIRouter(
    prefix="/transactions",
    tags=["Transactions"]
)


# 1. Get all transactions for a particular user
@router.get("/{user_id}")
def get_transactions(
    user_id: int,
    search: Optional[str] = None,
    transaction_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):

    with create_connection() as conn:
        cursor = conn.cursor()

        query = """
            SELECT
                t.transaction_id,
                t.transaction_ref,
                t.amount,
                t.transaction_type,
                t.transaction_date,
                t.description,
                s.filename
            FROM transactions t
            JOIN statements s
            ON t.statement_id = s.statement_id
            WHERE s.user_id = ?
        """

        params = [user_id]

        # Search by transaction ID or description
        if search:
            query += """
                AND (
                    t.transaction_ref LIKE ?
                    OR t.description LIKE ?
                )
            """
            params.extend([f"%{search}%", f"%{search}%"])

        # Filter by Debit or Credit
        if transaction_type:
            query += " AND t.transaction_type = ?"
            params.append(transaction_type)

        # Filter by starting date
        if start_date:
            query += " AND t.transaction_date >= ?"
            params.append(start_date)

        # Filter by ending date
        if end_date:
            query += " AND t.transaction_date <= ?"
            params.append(end_date)

        query += " ORDER BY t.transaction_date DESC"

        cursor.execute(query, params)

        rows = cursor.fetchall()

        columns = [
            "transaction_id",
            "transaction_ref",
            "amount",
            "transaction_type",
            "transaction_date",
            "description",
            "filename"
        ]

        transactions = [
            dict(zip(columns, row))
            for row in rows
        ]

        return {
            "user_id": user_id,
            "total_transactions": len(transactions),
            "transactions": transactions
        }


# 2. Get transaction summary
@router.get("/{user_id}/summary")
def get_transaction_summary(user_id: int):

    with create_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                SUM(
                    CASE
                        WHEN LOWER(transaction_type) = 'debit'
                        THEN amount ELSE 0
                    END
                ),
                SUM(
                    CASE
                        WHEN LOWER(transaction_type) = 'credit'
                        THEN amount ELSE 0
                    END
                ),
                COUNT(*)
            FROM transactions t
            JOIN statements s
            ON t.statement_id = s.statement_id
            WHERE s.user_id = ?
            """,
            (user_id,)
        )

        result = cursor.fetchone()

        return {
            "user_id": user_id,
            "total_debit": result[0] or 0,
            "total_credit": result[1] or 0,
            "total_transactions": result[2] or 0
        }