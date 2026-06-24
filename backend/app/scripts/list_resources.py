import argparse
import asyncio

from app.config.database import SessionFactory, dispose_database
from app.services.dataset_importer import get_resource_page


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read a paginated dataset resource page from PostgreSQL.")
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=20)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    async with SessionFactory() as session:
        resources = await get_resource_page(session, args.page, args.page_size)
    for resource in resources:
        print(f"id={resource.id} split={resource.dataset_split} path={resource.storage_key} text={resource.text[:80]!r}")
    print(f"page={args.page} page_size={args.page_size} returned={len(resources)}")
    await dispose_database()


if __name__ == "__main__":
    asyncio.run(main())
