"""Advisory scan of staged/ for leftover Google Docs export artifacts.

Flags, never blocks — the human review in PLAN.md §8 step 5 is still the real gate.
Heuristic regexes, not an HTML parser: cheap to run, meant to catch the obvious misses.
"""

from pathlib import Path
from re import IGNORECASE, compile as re_compile
from typing import Dict, List

_PATTERNS = {
    "inline style attribute": re_compile(r'style\s*=\s*["\']'),
    "font-family declaration": re_compile(r"font-family\s*:", IGNORECASE),
    "Google Docs internal id": re_compile(r'id\s*=\s*["\']docs-internal-guid-[^"\']*["\']'),
}


def lint_staged(client_dir: Path) -> Dict[str, List[str]]:
    staged_dir = client_dir / "staged"
    findings: Dict[str, List[str]] = {}

    if not staged_dir.exists():
        return findings

    for staged_file in sorted(staged_dir.rglob("*.html")):
        rel = staged_file.relative_to(staged_dir)
        path_str = str(rel.with_suffix(""))
        text = staged_file.read_text(encoding="utf-8", errors="replace")
        hits = [label for label, pattern in _PATTERNS.items() if pattern.search(text)]
        if hits:
            findings[path_str] = hits

    return findings
