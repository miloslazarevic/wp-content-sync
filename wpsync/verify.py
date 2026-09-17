"""Post-paste verification: diff staged/ against a fresh current/."""

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class VerifyMismatch:
    path: str
    reason: str


@dataclass
class VerifyResult:
    checked: int
    mismatches: List[VerifyMismatch]


def verify_client(client_dir: Path) -> VerifyResult:
    staged_dir = client_dir / "staged"
    current_dir = client_dir / "current"

    if not staged_dir.exists():
        return VerifyResult(checked=0, mismatches=[])

    mismatches = []
    checked = 0
    for staged_file in sorted(staged_dir.rglob("*.html")):
        rel = staged_file.relative_to(staged_dir)
        path_str = str(rel.with_suffix(""))
        checked += 1

        current_file = current_dir / rel
        if not current_file.exists():
            mismatches.append(
                VerifyMismatch(
                    path=path_str,
                    reason="missing from current/ (not pasted yet, or the page was removed)",
                )
            )
            continue

        if staged_file.read_bytes() != current_file.read_bytes():
            mismatches.append(
                VerifyMismatch(
                    path=path_str,
                    reason="differs from current/ (paste failed, or WordPress altered it on save)",
                )
            )

    return VerifyResult(checked=checked, mismatches=mismatches)
