"""Read-only importer for the mounted SpokenDialogueSum dataset."""

import csv
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audio_resource import AudioResource


DATASET_NAME = "spokendialoguesum"
SPLIT_PREFIX = "EmoDialogueSum_"
REQUIRED_SEGMENT_COLUMNS = {
    "dialog_speaker",
    "start",
    "end",
    "text",
    "emotion",
    "pitch_std",
    "speaking_rate",
    "summary",
    "emotional_summary",
}


@dataclass(frozen=True)
class ImportCandidate:
    name: str
    text: str
    metainfo: dict[str, Any]
    dataset_split: str
    storage_key: str
    file_size_bytes: int
    duration_ms: int | None


class DatasetFormatError(ValueError):
    pass


def iter_dialogue_directories(dataset_root: Path, splits: set[str] | None = None) -> Iterable[tuple[str, Path]]:
    """Yield dialogue directories from test/dev/train split roots in a stable order."""
    for split_root in sorted(dataset_root.glob(f"{SPLIT_PREFIX}*")):
        if not split_root.is_dir():
            continue
        split = split_root.name.removeprefix(SPLIT_PREFIX).lower()
        if splits and split not in splits:
            continue
        dialogue_dirs = (path for path in split_root.iterdir() if path.is_dir() and path.name.startswith("dialogue_"))
        yield from ((split, directory) for directory in sorted(dialogue_dirs, key=_dialogue_sort_key))


def _dialogue_sort_key(directory: Path) -> tuple[int, str]:
    suffix = directory.name.removeprefix("dialogue_")
    return (int(suffix) if suffix.isdigit() else 10**12, directory.name)


def build_candidate(dataset_root: Path, dataset_split: str, dialogue_dir: Path) -> ImportCandidate:
    """Parse one overlap WAV and its companion CSV/TSV without copying any audio."""
    overlap_audio = dialogue_dir / f"{dialogue_dir.name}_overlap.wav"
    segments_csv = dialogue_dir / "segmentation_overlap.csv"
    speakers_tsv = dialogue_dir / "speaker_prompt_meta.tsv"
    if not overlap_audio.is_file():
        raise DatasetFormatError(f"missing overlap audio: {overlap_audio}")
    if not segments_csv.is_file():
        raise DatasetFormatError(f"missing segmentation CSV: {segments_csv}")
    if not speakers_tsv.is_file():
        raise DatasetFormatError(f"missing speaker TSV: {speakers_tsv}")

    segments = _read_segments(segments_csv)
    speakers = _read_speakers(speakers_tsv)
    first_segment = segments[0]
    transcript = "\n".join(
        f"{segment['speaker']}: {segment['transcript']}" for segment in segments if segment["transcript"]
    )
    storage_key = overlap_audio.relative_to(dataset_root).as_posix()
    return ImportCandidate(
        name=overlap_audio.name,
        text=transcript,
        dataset_split=dataset_split,
        storage_key=storage_key,
        file_size_bytes=overlap_audio.stat().st_size,
        duration_ms=_wav_duration_ms(overlap_audio),
        metainfo={
            "dialogue_id": dialogue_dir.name,
            "resource_type": "overlap_dialogue",
            "fact_summary": first_segment["summary"],
            "emotional_summary": first_segment["emotional_summary"],
            "speakers": speakers,
            "segments": segments,
        },
    )


def _read_segments(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not REQUIRED_SEGMENT_COLUMNS.issubset(reader.fieldnames):
            raise DatasetFormatError(f"unexpected segmentation columns in {path}")
        segments = [
            {
                "speaker": _clean(row["dialog_speaker"]),
                "start_seconds": _as_float(row["start"]),
                "end_seconds": _as_float(row["end"]),
                "transcript": _clean(row["text"]),
                "emotion": _clean(row["emotion"]),
                "pitch_std": _as_float(row["pitch_std"]),
                "speaking_rate": _as_float(row["speaking_rate"]),
                "summary": _clean(row["summary"]),
                "emotional_summary": _clean(row["emotional_summary"]),
            }
            for row in reader
        ]
    if not segments:
        raise DatasetFormatError(f"no segments in {path}")
    return segments


def _read_speakers(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        required_columns = {"dialog_speaker", "file_name", "Gender", "Age"}
        if not reader.fieldnames or not required_columns.issubset(reader.fieldnames):
            raise DatasetFormatError(f"unexpected speaker columns in {path}")
        return {
            _clean(row["dialog_speaker"]): {
                "gender": _clean(row["Gender"]),
                "age": _clean(row["Age"]),
            }
            for row in reader
        }


def _wav_duration_ms(path: Path) -> int | None:
    try:
        with wave.open(str(path), "rb") as source:
            return round(source.getnframes() * 1000 / source.getframerate())
    except (OSError, wave.Error, EOFError, ZeroDivisionError):
        return None


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _as_float(value: str | None) -> float | None:
    cleaned = _clean(value)
    return float(cleaned) if cleaned else None


async def upsert_candidate(session: AsyncSession, candidate: ImportCandidate) -> None:
    values = {
        "name": candidate.name,
        "text": candidate.text,
        "metainfo": candidate.metainfo,
        "source_type": "dataset",
        "dataset_name": DATASET_NAME,
        "dataset_split": candidate.dataset_split,
        "storage_key": candidate.storage_key,
        "content_type": "audio/wav",
        "audio_format": "wav",
        "file_size_bytes": candidate.file_size_bytes,
        "duration_ms": candidate.duration_ms,
    }
    statement = insert(AudioResource).values(**values)
    statement = statement.on_conflict_do_update(
        constraint="uq_audio_resources_dataset_storage_key",
        set_={key: value for key, value in values.items() if key not in {"dataset_name", "storage_key"}},
    )
    await session.execute(statement)


async def get_resource_page(session: AsyncSession, page: int, page_size: int) -> list[AudioResource]:
    if page < 1 or not 1 <= page_size <= 100:
        raise ValueError("page must be >= 1 and page_size must be between 1 and 100")
    statement = (
        select(AudioResource)
        .where(AudioResource.dataset_name == DATASET_NAME)
        .order_by(AudioResource.dataset_split, AudioResource.storage_key)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list((await session.scalars(statement)).all())
