import argparse
import asyncio
import logging
from pathlib import Path

from app.config.database import SessionFactory, dispose_database
from app.config.settings import get_settings
from app.services.dataset_importer import DatasetFormatError, build_candidate, iter_dialogue_directories, upsert_candidate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import overlap dialogue metadata without copying source audio.")
    parser.add_argument("--dataset-root", type=Path, default=Path(get_settings().dataset_root))
    parser.add_argument("--split", action="append", choices=("test", "dev", "train"), help="Import only selected split(s).")
    parser.add_argument("--limit", type=int, help="Stop after this many candidates; useful for a smoke test.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate files without writing to PostgreSQL.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    dataset_root = args.dataset_root.resolve()
    if not dataset_root.is_dir():
        raise SystemExit(f"Dataset root does not exist: {dataset_root}")

    imported = skipped = scanned = 0
    async with SessionFactory() as session:
        for dataset_split, dialogue_dir in iter_dialogue_directories(dataset_root, set(args.split or [])):
            if args.limit is not None and scanned >= args.limit:
                break
            scanned += 1
            try:
                candidate = build_candidate(dataset_root, dataset_split, dialogue_dir)
            except DatasetFormatError as exc:
                skipped += 1
                logging.warning("Skipping %s: %s", dialogue_dir, exc)
                continue
            if not args.dry_run:
                await upsert_candidate(session, candidate)
            imported += 1
        if args.dry_run:
            await session.rollback()
        else:
            await session.commit()

    print(f"scanned={scanned} imported={imported} skipped={skipped} dry_run={args.dry_run}")
    await dispose_database()


if __name__ == "__main__":
    asyncio.run(main())
