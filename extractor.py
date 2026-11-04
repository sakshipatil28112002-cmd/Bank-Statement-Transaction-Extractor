from io import BytesIO
import re
import pandas as pd
import pdfplumber


def extract_pdf(file_bytes, password=None):

    transactions = []

    # --------------------------------
    # 1. DATE PATTERN
    # --------------------------------

    date_pattern = re.compile(
        r"\b(?:"
        r"\d{2}[-/]\d{2}[-/]\d{4}"
        r"|\d{4}[-/]\d{2}[-/]\d{2}"
        r")\b"
    )

    # --------------------------------
    # 2. AMOUNT PATTERN
    # --------------------------------

    amount_pattern = re.compile(
        r"(?<![\w/])"
        r"(?:INR|Rs\.?|₹)?\s*"
        r"(\d{1,3}(?:,\d{2,3})+|\d+)"
        r"(?:\.(\d{2}))?"
        r"(?![\w/])",
        re.IGNORECASE
    )

    # --------------------------------
    # 3. TRANSACTION ID PATTERNS
    # --------------------------------

    upi_pattern = re.compile(
        r"\bUPI[/:\-]\s*([0-9]{8,18})\b",
        re.IGNORECASE
    )

    neft_pattern = re.compile(
        r"\bNEFT[/:\-]\s*([A-Z0-9]{8,22})\b",
        re.IGNORECASE
    )

    imps_pattern = re.compile(
        r"\bIMPS[/:\-]\s*([A-Z0-9]{8,22})\b",
        re.IGNORECASE
    )

    generic_id_pattern = re.compile(
        r"\b(?:UTR|RRN|REF|TXN|CHEQUE|CHQ)"
        r"\s*[:#/\-]?\s*([A-Z0-9]{6,22})\b",
        re.IGNORECASE
    )

    # --------------------------------
    # 4. TRANSACTION TYPE
    # --------------------------------

    debit_pattern = re.compile(
        r"(?:/|\b)(?:DR|DEBIT)(?:/|\b)",
        re.IGNORECASE
    )

    credit_pattern = re.compile(
        r"(?:/|\b)(?:CR|CREDIT)(?:/|\b)",
        re.IGNORECASE
    )

    # --------------------------------
    # 5. EXTRACT TRANSACTION ID
    # --------------------------------

    def extract_transaction_id(line):

        patterns = [
            upi_pattern,
            neft_pattern,
            imps_pattern,
            generic_id_pattern
        ]

        for pattern in patterns:

            match = pattern.search(line)

            if match:
                return match.group(1)

        return None

    # --------------------------------
    # 6. EXTRACT TRANSACTION TYPE
    # --------------------------------

    def extract_transaction_type(line):

        if debit_pattern.search(line):
            return "Debit"

        elif credit_pattern.search(line):
            return "Credit"

        return "Unknown"

    # --------------------------------
    # 7. CLEAN DESCRIPTION
    # --------------------------------

    def clean_description(line, date_match, amount_match):

        description = line

        # Remove the date
        if date_match:
            description = (
                description[:date_match.start()]
                + description[date_match.end():]
            )

        # Remove the selected transaction amount
        if amount_match:
            description = (
                description[:amount_match.start()]
                + description[amount_match.end():]
            )

        # Remove leading serial number
        description = re.sub(
            r"^\s*\d+\s+",
            "",
            description
        )

        # Remove extra spaces
        description = re.sub(
            r"\s+",
            " ",
            description
        ).strip() 

        return description

    # --------------------------------
    # 8. OPEN PDF
    # --------------------------------

    with pdfplumber.open(
        BytesIO(file_bytes),
        password=password or ""
    ) as pdf:

        for page in pdf.pages:

            text = page.extract_text()

            if not text:
                continue

            lines = text.split("\n")

            for line in lines:

                line = line.strip()

                if not line:
                    continue

                lower_line = line.lower()

                # Skip unwanted lines
                skip_words = [
                    "opening balance",
                    "closing balance",
                    "statement summary",
                    "page total",
                    "total debit",
                    "total credit"
                ]

                if any(word in lower_line for word in skip_words):
                    continue

                # --------------------------------
                # DATE EXTRACTION
                # --------------------------------

                date_match = date_pattern.search(line)

                if not date_match:
                    continue

                date_val = date_match.group()

                # --------------------------------
                # AMOUNT EXTRACTION
                # --------------------------------

                amount_matches = list(
                    amount_pattern.finditer(line)
                )

                if not amount_matches:
                    continue

                # Use the last monetary value
                amount_match = amount_matches[-1]

                amount_val = float(
                    amount_match.group(1).replace(",", "")
                )

                if amount_match.group(2):
                    amount_val += (
                        float(amount_match.group(2)) / 100
                    )

                # --------------------------------
                # TRANSACTION TYPE
                # --------------------------------

                type_str = extract_transaction_type(line)

                # --------------------------------
                # TRANSACTION ID
                # --------------------------------

                tx_ref = extract_transaction_id(line)

                # --------------------------------
                # DESCRIPTION
                # --------------------------------

                description = clean_description(
                    line,
                    date_match,
                    amount_match
                )

                # --------------------------------
                # SAVE TRANSACTION
                # --------------------------------

                transactions.append({

                    "Date": date_val,

                    "Description": description,

                    "Transaction ID": (
                        tx_ref if tx_ref else "FLAGGED_MISSING_ID"
                    ),

                    "Amount": round(amount_val, 2),

                    "Type": type_str

                })

    # --------------------------------
    # 9. RETURN DATAFRAME
    # --------------------------------

    columns = [
        "Date",
        "Description",
        "Transaction ID",
        "Amount",
        "Type"
    ]

    return pd.DataFrame(
        transactions,
        columns=columns
    )