"""Scope filtering and file/CSV writing."""

import csv
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from wpsync.config import DumpConfig, Profile
from wpsync.db import connect, fetch_page_templates, fetch_pages
from wpsync.paths import resolve_paths
from wpsync.summary import render_summary_html


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


def _normalize_line_endings(content: str) -> str:
    # WordPress's own wpautop() does exactly this ("\r\n"/"\r" -> "\n") as its
    # first step before rendering, so this changes zero rendered output — it's
    # not a content transform, just matching what WP already treats as equivalent.
    return content.replace("\r\n", "\n").replace("\r", "\n")


def _has_content(row: dict) -> bool:
    return bool((row["post_content"] or "").strip())


def write_current(client_dir: Path, pages: Dict[str, dict]) -> None:
    current_dir = client_dir / "current"
    _clear_directory(current_dir)
    for path, row in pages.items():
        if not _has_content(row):
            # No post_content -- usually ACF/flexible-content or a page builder.
            # The page is still listed in pages.csv and summary.html; there's just
            # nothing to write here. See PLAN.md §11.
            continue
        file_path = current_dir / f"{path}.html"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        content = _normalize_line_endings(row["post_content"])
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
                    f"current/{path}.html" if _has_content(row) else "",
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


def _warn_empty_content(pages: Dict[str, dict], warnings: List[str]) -> None:
    empty = [path for path, row in pages.items() if not _has_content(row)]
    if not empty:
        return
    warnings.append(
        f"{len(empty)} page(s) in scope have empty post_content — this usually means "
        "the page is built with ACF/flexible-content fields or a page builder rather "
        "than the editor. No current/<path>.html is written for these; they're still "
        "listed in pages.csv and summary.html, flagged as empty. See PLAN.md §11. "
        "Affected paths: " + ", ".join(sorted(empty))
    )


def list_client(profile: Profile) -> ListResult:
    conn = connect(profile.database)
    try:
        rows = fetch_pages(
            conn,
            profile.database.table_prefix,
            profile.dump.post_types,
            profile.dump.post_status,
        )
        templates = fetch_page_templates(
            conn, profile.database.table_prefix, [r["ID"] for r in rows]
        )
    finally:
        conn.close()

    resolved, warnings = resolve_paths(rows)
    for row in resolved.values():
        row["page_template"] = templates.get(row["ID"]) or "default"

    scoped = apply_scope(resolved, profile.dump)
    _warn_empty_content(scoped, warnings)
    return ListResult(pages=scoped, warnings=warnings)


def write_summary_html(client_dir: Path, client_name: str, label: str, pages: Dict[str, dict], warnings: List[str]) -> None:
    html = render_summary_html(client_name, label, pages, warnings)
    (client_dir / "summary.html").write_text(html, encoding="utf-8")


def dump_client(profile: Profile) -> DumpResult:
    result = list_client(profile)
    write_current(profile.client_dir, result.pages)
    write_pages_csv(profile.client_dir, result.pages)
    write_summary_html(profile.client_dir, profile.name, profile.label, result.pages, result.warnings)
    return DumpResult(page_count=len(result.pages), warnings=result.warnings)
