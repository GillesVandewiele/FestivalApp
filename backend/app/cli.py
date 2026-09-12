import asyncio
import getpass
import sys

from .config import get_settings
from .db import ensure_indexes, get_client
from .models.identity import User
from .security import hash_password


async def create_organiser(email: str, password: str) -> None:
    settings = get_settings()
    client = get_client(settings.mongo_uri)
    db = client[settings.mongo_db]
    await ensure_indexes(db)

    if await db.users.find_one({"email": email}):
        print(f"User {email} already exists.")
        return

    user = User(email=email, password_hash=hash_password(password))
    await db.users.insert_one(user.to_mongo())
    print(f"Created organiser {email} ({user.id})")
    client.close()


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] != "create-organiser":
        print("usage: python -m app.cli create-organiser <email>")
        raise SystemExit(1)

    password = getpass.getpass("Password: ")
    if len(password) < 12:
        print("Password must be at least 12 characters.")
        raise SystemExit(1)
    if password != getpass.getpass("Repeat: "):
        print("Passwords do not match.")
        raise SystemExit(1)

    asyncio.run(create_organiser(sys.argv[2], password))


if __name__ == "__main__":
    main()
