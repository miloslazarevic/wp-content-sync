"""Scope filtering and file/CSV writing."""

import csv
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from wpsync.config import DumpConfig, Profile
from wpsync.db import connect, fetch_pages
from wpsync.paths import resolve_paths


def _normalize_scope_path(path: str) -> str:
    return path.strip("/")


def apply_scope(paths: Dict[str, dict], dump_config: DumpConfig) -> Dict[str, dict]:
    include = {_normalize_scope_path(p) for p in dump_config.include}
    exclude = {_normalize_scope_path(p) for p in dump_config.exclude}

    result = {}
    for path, row in paths.items():
        if include and path not in include:
            continue
        if path in exclude:
            continue
        result[path] = row
    return result


def _clear_directory(dir_path: Path) -> None:
    if dir_path.exists():
        shutil.rmtree(dir_path)
    dir_path.mkdir(parents=True, exist_ok=True)


def write_current(client_dir: Path, pages: Dict[str, dict]) -> None:
    current_dir = client_dir / "current"
    _clear_directory(current_dir)
    for path, row in pages.items():
        file_path = current_dir / f"{path}.html"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        content = row["post_content"] or ""
        file_path.write_bytes(content.encode("utf-8"))


def write_pages_csv(client_dir: Path, pages: Dict[str, dict]) -> None:
    csv_path = client_dir / "pages.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "path", "file", "title", "status", "modified"])
        for path in sorted(pages):
            row = pages[path]
            writer.writerow(
                [
                    row["ID"],
                    path,
                    f"current/{path}.html",
                    row["post_title"],
                    row["post_status"],
                    row["post_modified"],
                ]
            )


@dataclass
class ListResult:
    pages: Dict[str, dict]
    warnings: List[str]


@dataclass
class DumpResult:
    page_count: int
    warnings: List[str]


def list_client(profile: Profile) -> ListResult:
    conn = connect(profile.database)
    try:
        rows = fetch_pages(
            conn,
            profile.database.table_prefix,
            profile.dump.post_types,
            profile.dump.post_status,
        )
    finally:
        conn.close()

    resolved, warnings = resolve_paths(rows)
    scoped = apply_scope(resolved, profile.dump)
    return ListResult(pages=scoped, warnings=warnings)


def dump_client(profile: Profile) -> DumpResult:
    result = list_client(profile)
    write_current(profile.client_dir, result.pages)
    write_pages_csv(profile.client_dir, result.pages)
    return DumpResult(page_count=len(result.pages), warnings=result.warnings)
