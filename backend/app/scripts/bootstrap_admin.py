import argparse
import asyncio
import getpass

from sqlalchemy import select

from app.config.database import SessionFactory, dispose_database
from app.models.user import User
from app.utils.security import hash_password


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or promote one administrator account.")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", help="Required when creating a new account; omit to enter it securely.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    async with SessionFactory() as session:
        user = await session.scalar(select(User).where(User.username == args.username))
        if user is None:
            password = args.password or getpass.getpass("Admin password: ")
            if len(password) < 8:
                raise SystemExit("Admin password must contain at least 8 characters.")
            user = User(username=args.username, password_hash=hash_password(password), role="admin", is_active=True)
            session.add(user)
            action = "created"
        else:
            user.role = "admin"
            user.is_active = True
            action = "promoted"
        await session.commit()
        print(f"{action} admin username={user.username} id={user.id}")
    await dispose_database()


if __name__ == "__main__":
    asyncio.run(main())
