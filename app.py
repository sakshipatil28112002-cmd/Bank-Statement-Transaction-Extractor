import hashlib
import re
from datetime import datetime
import pandas as pd
import streamlit as st

from database import (
    create_connection,
    create_tables,
    delete_user_profile,
    update_user_profile,
)
from extractor import extract_pdf

# 1. PAGE SETUP
st.set_page_config(
    page_title="Bank Statement Extractor",
    page_icon="🏦",
    layout="wide"
)
create_tables()

st.title("🏦 Bank Statement Transaction Extractor")
st.write("Upload your bank statement PDF to extract, search, and export transaction details.")

# 2. PROFILE MANAGEMENT (SIDEBAR)
st.sidebar.header("User Profiles")

# Form: Create New Profile
with st.sidebar.expander("➕ Create Profile", expanded=False):
    with st.form("create_user_form", clear_on_submit=True):
        new_name = st.text_input("Name", key="new_name")
        new_email = st.text_input("Email", key="new_email")
        new_bank = st.text_input("Bank Name", key="new_bank")
        submit_create = st.form_submit_button("Create Profile")

        if submit_create:
            if new_name.strip() and new_email.strip() and new_bank.strip():
                try:
                    with create_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO users (name, email, bank_name) VALUES (?, ?, ?)",
                            (new_name.strip(), new_email.strip(), new_bank.strip())
                        )
                        conn.commit()
                    st.sidebar.success("Profile created successfully!")
                    st.rerun()
                except Exception:
                    st.sidebar.error("Email may already be registered.")
            else:
                st.sidebar.warning("All fields are required.")

# Load Existing Users
with create_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, name, email, bank_name FROM users")
    users = cursor.fetchall()

if not users:
    st.info("👋 No profiles found. Please create a user profile in the sidebar to get started.")
    st.stop()

# Profile Selector
user_options = {f"{u[1]} ({u[2]}) - {u[3]}": u[0] for u in users}
selected_user_label = st.sidebar.selectbox(
    "Active Profile",
    list(user_options.keys()),
    key="active_profile_selector"
)
user_id = user_options[selected_user_label]
current_user = next(u for u in users if u[0] == user_id)

# Form: Edit / Delete Active Profile
with st.sidebar.expander("⚙️ Manage Profile", expanded=False):
    edit_name = st.text_input("Update Name", value=current_user[1], key="edit_name_input")
    edit_bank = st.text_input("Update Bank", value=current_user[3], key="edit_bank_input")
    
    col_up, col_del = st.columns(2)
    with col_up:
        if st.button("Save Changes", key="btn_save_profile"):
            update_user_profile(user_id, edit_name.strip(), edit_bank.strip())
            st.sidebar.success("Profile updated!")
            st.rerun()

    with col_del:
        if st.button("🗑️ Delete", type="primary", key="btn_delete_profile"):
            delete_user_profile(user_id)
            st.sidebar.warning("Profile deleted.")
            st.rerun()

# 3. PDF UPLOAD & PARSING
st.header("Upload Bank Statement")
uploaded_file = st.file_uploader("Upload bank statement (PDF)", type=["pdf"], key="pdf_file_uploader")
pdf_password = st.text_input("Password (leave blank if unprotected)", type="password", key="pdf_pwd_input")

if uploaded_file is not None:
    if st.button("Extract Transactions", key="btn_extract_tx"):
        file_bytes = uploaded_file.getvalue()
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        try:
            with create_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT statement_id FROM statements WHERE user_id = ? AND file_hash = ?",
                    (user_id, file_hash)
                )
                existing = cursor.fetchone()

                if existing:
                    st.warning("⚠️ This statement has already been uploaded for this user.")
                else:
                    with st.spinner("Extracting transactions..."):
                        df = extract_pdf(file_bytes, pdf_password)

                    if df.empty:
                        st.warning("No transactions detected. Please verify PDF format or password.")
                    else:
                        cursor.execute(
                            "INSERT INTO statements (user_id, filename, upload_date, file_hash) VALUES (?, ?, ?, ?)",
                            (user_id, uploaded_file.name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), file_hash)
                        )
                        statement_id = cursor.lastrowid

                        for _, row in df.iterrows():
                            cursor.execute("""
                                INSERT INTO transactions (
                                    statement_id, transaction_ref, amount, transaction_type, transaction_date, description
                                ) VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                statement_id,
                                row["Transaction ID"],
                                row["Amount"],
                                row["Type"],
                                row["Date"],
                                row["Description"]
                            ))
                        conn.commit()
                        st.success(f"Successfully saved {len(df)} transactions.")
                        st.rerun()
        except Exception as e:
            st.error("Error processing PDF statement.")
            st.exception(e)

# 4. VIEW, SEARCH & FILTER
st.divider()
st.header("Transaction History & Analytics")

with create_connection() as conn:
    query = """
    SELECT 
        t.transaction_id,
        t.transaction_ref AS "Transaction ID",
        t.amount AS "Amount",
        t.transaction_type AS "Type",
        t.transaction_date AS "Date",
        t.description AS "Description",
        s.filename AS "Statement"
    FROM transactions t
    JOIN statements s ON t.statement_id = s.statement_id
    WHERE s.user_id = ?
    ORDER BY t.transaction_id DESC
    """
    df_history = pd.read_sql_query(query, conn, params=(user_id,))

if df_history.empty:
    st.info("No transaction history found. Upload a statement above.")
else:
    # Auto-repair logic for previously saved rows marked Unknown / Not Found
    rows_to_update = []
    for idx, row in df_history.iterrows():
        curr_type = str(row["Type"]).strip()
        curr_ref = str(row["Transaction ID"]).strip()
        desc = str(row["Description"]).strip()
        updated = False

        if curr_type in ["Unknown", "None", ""]:
            desc_upper = desc.upper()
            if "/CR/" in desc_upper or " CR " in desc_upper or desc_upper.endswith(" CR"):
                curr_type = "Credit"
            else:
                curr_type = "Debit"
            df_history.at[idx, "Type"] = curr_type
            updated = True

        if curr_ref in ["Not Found", "FLAGGED_MISSING_ID", "None", ""]:
            m = re.search(r"UPI[/:]\s*([0-9]{8,18})", desc, re.IGNORECASE)
            if m:
                curr_ref = m.group(1)
                df_history.at[idx, "Transaction ID"] = curr_ref
                updated = True

        if updated:
            rows_to_update.append((curr_type, curr_ref, int(row["transaction_id"])))

    if rows_to_update:
        with create_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "UPDATE transactions SET transaction_type = ?, transaction_ref = ? WHERE transaction_id = ?",
                rows_to_update
            )
            conn.commit()

    df_history["Amount"] = pd.to_numeric(df_history["Amount"], errors="coerce").fillna(0.0)

    # Filter Controls
    with st.expander("🔍 Search & Filters", expanded=True):
        col_f1, col_f2, col_f3 = st.columns(3)
        search_id = col_f1.text_input("Search ID / Ref", key="filter_search_id")
        type_filter = col_f2.selectbox("Type", ["All", "Debit", "Credit"], key="filter_tx_type")

        min_amt = float(df_history["Amount"].min())
        max_amt = float(df_history["Amount"].max())
        if min_amt >= max_amt:
            max_amt = min_amt + 100.0
        amt_range = col_f3.slider(
            "Amount Range",
            min_value=0.0,
            max_value=max_amt,
            value=(0.0, max_amt),
            key="filter_amt_slider"
        )

    # Filter Application
    filtered_df = df_history.copy()
    if search_id.strip():
        filtered_df = filtered_df[
            filtered_df["Transaction ID"].astype(str).str.contains(search_id.strip(), case=False, na=False)
        ]
    if type_filter != "All":
        filtered_df = filtered_df[filtered_df["Type"] == type_filter]
    filtered_df = filtered_df[
        (filtered_df["Amount"] >= amt_range[0]) & (filtered_df["Amount"] <= amt_range[1])
    ]

    # Metrics
    debit_total = filtered_df.loc[filtered_df["Type"] == "Debit", "Amount"].sum()
    credit_total = filtered_df.loc[filtered_df["Type"] == "Credit", "Amount"].sum()

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Debit", f"₹ {debit_total:,.2f}")
    m2.metric("Total Credit", f"₹ {credit_total:,.2f}")
    m3.metric("Filtered Records", len(filtered_df))

    # Display Table
    display_cols = ["Transaction ID", "Amount", "Type", "Date", "Description", "Statement"]
    st.dataframe(filtered_df[display_cols], use_container_width=True)

    # Export CSV
    csv_data = filtered_df[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Export Filtered Results to CSV",
        data=csv_data,
        file_name="bank_transactions.csv",
        mime="text/csv",
        key="btn_csv_export"
    )