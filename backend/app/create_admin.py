"""Privately provision the first Trikaaya administrator from a trusted terminal.

Run from the backend directory: python -m app.create_admin
No HTTP/public registration endpoint exists for administrator creation.
"""
import os
import getpass
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from pwdlib import PasswordHash


def main():
    load_dotenv()
    mongo_url = os.getenv("MONGODB_URL")
    if not mongo_url:
        raise SystemExit("MONGODB_URL is required in backend/.env")
    database_name = os.getenv("MONGODB_DB", "trikaaya_sports")
    email = input("Admin email: ").strip().lower()
    if not email or "@" not in email:
        raise SystemExit("Enter a valid admin email address.")
    password = getpass.getpass("New admin password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm admin password: ")
    if len(password) < 12:
        raise SystemExit("Admin password must contain at least 12 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=8000)
    try:
        client.admin.command("ping")
        admins = client[database_name].admins
        admins.create_index("email", unique=True)
        if admins.find_one({"email": email}):
            raise SystemExit("An Admin account already exists for this email. No changes were made.")
        password_hash = PasswordHash.recommended().hash(password)
        admins.insert_one({
            "email": email,
            "password_hash": password_hash,
            "active": True,
            "created_at": datetime.now(timezone.utc),
            "created_via": "private_cli_bootstrap",
        })
        print(f"Admin account created for {email}. Keep this account's credentials private.")
    except DuplicateKeyError:
        raise SystemExit("An Admin account already exists for this email.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
