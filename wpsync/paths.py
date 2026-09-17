"""Parent-chain path derivation from raw post rows."""

from typing import Dict, List, Tuple

MAX_WALK_DEPTH = 50


def _slug_for(row: dict) -> str:
    return row["post_name"] or f"untitled-{row['ID']}"


def _build_chain(row: dict, by_id: Dict[int, dict], warnings: List[str]) -> List[dict]:
    chain = [row]
    visited = {row["ID"]}
    current = row
    depth = 0

    while current["post_parent"]:
        depth += 1
        if depth > MAX_WALK_DEPTH:
            warnings.append(
                f"post ID {row['ID']} ('{row['post_title']}'): parent chain exceeds "
                f"{MAX_WALK_DEPTH} levels, likely a cycle — treating as root level"
            )
            return [row]

        parent = by_id.get(current["post_parent"])
        if parent is None:
            warnings.append(
                f"post ID {current['ID']} ('{current['post_title']}'): post_parent "
                f"{current['post_parent']} is missing or out of dump scope — "
                f"treating '{_slug_for(row)}' branch as root level"
            )
            break

        if parent["ID"] in visited:
            warnings.append(
                f"post ID {row['ID']} ('{row['post_title']}'): parent cycle detected "
                f"(post ID {parent['ID']} repeats) — treating as root level"
            )
            return [row]

        visited.add(parent["ID"])
        chain.append(parent)
        current = parent

    chain.reverse()
    return chain


def resolve_paths(rows: List[dict]) -> Tuple[Dict[str, dict], List[str]]:
    """Derive a full parent-chain path for every row.

    Returns (path -> row-with-'path'-added, warnings). Rows are processed in
    ascending ID order so path collisions resolve deterministically: the
    lower-ID post always keeps the bare path, later ones get an ID suffix.
    """
    warnings: List[str] = []
    sorted_rows = sorted(rows, key=lambda r: r["ID"])
    by_id = {r["ID"]: r for r in sorted_rows}

    path_owner: Dict[str, int] = {}
    output: Dict[str, dict] = {}

    for row in sorted_rows:
        chain = _build_chain(row, by_id, warnings)
        base_path = "/".join(_slug_for(r) for r in chain)

        path = base_path
        if path in path_owner:
            path = f"{base_path}-{row['ID']}"
            warnings.append(
                f"path collision: '{base_path}' is already used by post ID "
                f"{path_owner[base_path]} — post ID {row['ID']} "
                f"('{row['post_title']}') renamed to '{path}'"
            )

        path_owner[path] = row["ID"]
        resolved_row = dict(row)
        resolved_row["path"] = path
        output[path] = resolved_row

    return output, warnings
