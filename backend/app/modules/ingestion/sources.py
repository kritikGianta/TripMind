"""Reading a dataset: a ZIP archive or a folder of CSV, TSV, JSON, JSONL or XLSX files.

Archives are read in memory member by member and never extracted to disk, so paths inside the
archive cannot escape. Size and member-count limits guard against archive bombs.
"""

from __future__ import annotations

import fnmatch
import hashlib
import io
import json
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

import pandas as pd

from app.core.errors import ValidationFailed

TABLE_SUFFIXES = {".csv", ".tsv", ".txt", ".json", ".jsonl", ".ndjson", ".xlsx"}
_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


class SourceError(ValidationFailed):
    code = "SOURCE_INVALID"
    message = "The dataset could not be read."


@dataclass(frozen=True)
class Table:
    """One parsed file. All values are kept as strings; typing happens in the parsers."""

    name: str
    frame: pd.DataFrame
    encoding: str | None


class DatasetSource(Protocol):
    name: str
    sha256: str

    def members(self) -> list[str]: ...

    def read_bytes(self, member: str) -> bytes: ...


class ZipSource:
    def __init__(self, data: bytes, *, name: str, max_members: int, max_uncompressed_mb: int):
        self.name = name
        self.sha256 = hashlib.sha256(data).hexdigest()
        try:
            self._zip = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise SourceError("The upload is not a valid ZIP archive.") from exc
        infos = [i for i in self._zip.infolist() if not i.is_dir() and _is_data_member(i.filename)]
        if len(infos) > max_members:
            raise SourceError(f"The archive has more than {max_members} files.")
        total = sum(i.file_size for i in infos)
        if total > max_uncompressed_mb * 1024 * 1024:
            raise SourceError(f"The archive expands to more than {max_uncompressed_mb} MB.")
        self._infos = {i.filename: i for i in infos}

    def members(self) -> list[str]:
        return sorted(self._infos)

    def read_bytes(self, member: str) -> bytes:
        info = self._infos[member]
        with self._zip.open(info) as handle:
            # Read one byte past the declared size: a lying header cannot inflate past it.
            data = handle.read(info.file_size + 1)
        if len(data) > info.file_size:
            raise SourceError(f"{member} is larger than its archive header declares.")
        return data


class DirectorySource:
    def __init__(self, root: Path) -> None:
        if not root.is_dir():
            raise SourceError(f"{root} is not a folder.")
        self.name = root.name
        self._root = root
        self._files = {
            p.relative_to(root).as_posix(): p
            for p in sorted(root.rglob("*"))
            if p.is_file() and _is_data_member(p.relative_to(root).as_posix())
        }
        digest = hashlib.sha256()
        for rel, path in self._files.items():
            digest.update(rel.encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        self.sha256 = digest.hexdigest()

    def members(self) -> list[str]:
        return list(self._files)

    def read_bytes(self, member: str) -> bytes:
        return self._files[member].read_bytes()


def open_source(path: Path, *, max_members: int, max_uncompressed_mb: int) -> DatasetSource:
    if path.is_dir():
        return DirectorySource(path)
    if path.suffix.lower() == ".zip":
        return ZipSource(
            path.read_bytes(),
            name=path.name,
            max_members=max_members,
            max_uncompressed_mb=max_uncompressed_mb,
        )
    raise SourceError("A dataset must be a .zip archive or a folder.")


def _is_data_member(name: str) -> bool:
    path = PurePosixPath(name)
    if any(part.startswith((".", "__MACOSX")) for part in path.parts):
        return False
    return path.suffix.lower() in TABLE_SUFFIXES


def find_member(source: DatasetSource, pattern: str) -> str | None:
    """First member whose path or basename matches the glob, case-insensitively."""
    lowered = pattern.lower()
    for member in source.members():
        lower = member.lower()
        if fnmatch.fnmatch(lower, lowered) or fnmatch.fnmatch(PurePosixPath(lower).name, lowered):
            return member
    return None


def _decode(data: bytes) -> tuple[str, str]:
    for encoding in _ENCODINGS:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise SourceError("The file is not valid text in any supported encoding.")


def _records_frame(records: object, member: str, json_path: str | None) -> pd.DataFrame:
    if isinstance(records, dict):
        if json_path:
            records = records.get(json_path)
        else:
            # A single top-level list inside an object, e.g. {"hotels": [...]}.
            lists = [v for v in records.values() if isinstance(v, list)]
            records = lists[0] if len(lists) == 1 else None
    if not isinstance(records, list):
        raise SourceError(f"{member}: expected a list of records.")
    return pd.json_normalize(records, sep="_")


def read_table(
    source: DatasetSource,
    member: str,
    *,
    fmt: str = "auto",
    delimiter: str | None = None,
    sheet: str | None = None,
    json_path: str | None = None,
) -> Table:
    suffix = PurePosixPath(member).suffix.lower()
    kind = (
        fmt
        if fmt != "auto"
        else {
            ".tsv": "tsv",
            ".json": "json",
            ".jsonl": "jsonl",
            ".ndjson": "jsonl",
            ".xlsx": "xlsx",
        }.get(suffix, "csv")
    )
    data = source.read_bytes(member)
    encoding: str | None = None
    try:
        if kind == "xlsx":
            frame = pd.read_excel(io.BytesIO(data), sheet_name=sheet or 0, dtype=str)
        else:
            text, encoding = _decode(data)
            if kind == "json":
                frame = _records_frame(json.loads(text), member, json_path)
            elif kind == "jsonl":
                rows = [json.loads(line) for line in text.splitlines() if line.strip()]
                frame = _records_frame(rows, member, None)
            else:
                sep = delimiter or ("\t" if kind == "tsv" else None)
                frame = pd.read_csv(
                    io.StringIO(text),
                    sep=sep,
                    engine="python",
                    dtype=str,
                    keep_default_na=False,
                    skipinitialspace=True,
                )
    except (ValueError, json.JSONDecodeError, pd.errors.ParserError) as exc:
        raise SourceError(f"{member} could not be parsed: {exc}") from exc

    frame = frame.astype("object").where(frame.notna(), None)
    frame.columns = [str(c).strip() for c in frame.columns]
    frame = frame.map(_clean_cell).astype("object")
    frame = frame.where(frame.notna(), None)
    # Index = the row number a person sees in the file (line 1 is the header in tabular files).
    first = 2 if kind in {"csv", "tsv", "xlsx"} else 1
    frame.index = pd.RangeIndex(start=first, stop=first + len(frame))
    return Table(name=member, frame=frame, encoding=encoding)


def _clean_cell(value: object) -> object:
    """Strings are stripped, blanks become None, JSON lists stay lists, other scalars become str."""
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, float) and value != value:  # NaN
        return None
    text = value.strip() if isinstance(value, str) else str(value)
    return text or None


def iter_tables(source: DatasetSource) -> Iterator[Table]:
    for member in source.members():
        yield read_table(source, member)
