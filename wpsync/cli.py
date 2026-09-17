"""Command-line entry point: init, list, dump, dump --all."""

import argparse
import shutil
import sys
from pathlib import Path

from wpsync.config import ConfigError, load_profile
from wpsync.db import DatabaseError
from wpsync.dump import dump_client, list_client
from wpsync.lint import lint_staged
from wpsync.verify import verify_client

REPO_ROOT = Path(__file__).resolve().parent.parent
CLIENTS_DIR = REPO_ROOT / "clients"
TEMPLATE_DIR = CLIENTS_DIR / "_template"


def _print_warnings(warnings) -> None:
    if not warnings:
        return
    print(f"\n{len(warnings)} warning(s):", file=sys.stderr)
    for w in warnings:
        print(f"  - {w}", file=sys.stderr)


def cmd_init(client_name: str) -> int:
    target = CLIENTS_DIR / client_name
    if target.exists():
        print(f"clients/{client_name} already exists; not overwriting", file=sys.stderr)
        return 1
    shutil.copytree(TEMPLATE_DIR, target)
    print(f"Created clients/{client_name} from template.")
    print("Fill in profile.yml, then run: python -m wpsync list " + client_name)
    return 0


def cmd_list(client_name: str) -> int:
    client_dir = CLIENTS_DIR / client_name
    profile = load_profile(client_dir)
    result = list_client(profile)

    for path in sorted(result.pages):
        row = result.pages[path]
        print(f"{row['ID']:>6}  {path:<50} {row['post_status']:<10} {row['post_title']}")

    print(f"\n{len(result.pages)} page(s)")
    _print_warnings(result.warnings)
    return 0


def cmd_dump(client_name: str) -> int:
    client_dir = CLIENTS_DIR / client_name
    profile = load_profile(client_dir)
    result = dump_client(profile)
    print(f"{client_name}: dumped {result.page_count} page(s)")
    _print_warnings(result.warnings)
    return 0


def cmd_verify(client_name: str) -> int:
    client_dir = CLIENTS_DIR / client_name
    result = verify_client(client_dir)

    if result.checked == 0:
        print("No staged/ files found to verify.")
        return 0

    for m in result.mismatches:
        print(f"MISMATCH  {m.path}: {m.reason}")

    ok_count = result.checked - len(result.mismatches)
    print(f"\n{ok_count}/{result.checked} page(s) match current/")
    return 1 if result.mismatches else 0


def cmd_lint(client_name: str) -> int:
    client_dir = CLIENTS_DIR / client_name
    findings = lint_staged(client_dir)

    if not findings:
        print("No Google Docs export artifacts found in staged/.")
        return 0

    for path, hits in findings.items():
        print(f"{path}: {', '.join(hits)}")

    print(f"\n{len(findings)} file(s) flagged — advisory only, review before pasting.")
    return 1


def cmd_dump_all() -> int:
    succeeded = []
    failed = []

    for client_dir in sorted(CLIENTS_DIR.iterdir()):
        if not client_dir.is_dir() or client_dir.name == "_template":
            continue
        if not (client_dir / "profile.yml").exists():
            continue
        try:
            profile = load_profile(client_dir)
            result = dump_client(profile)
            succeeded.append((client_dir.name, result))
        except (ConfigError, DatabaseError) as e:
            failed.append((client_dir.name, str(e)))

    print("\nSummary:")
    for name, result in succeeded:
        print(f"  OK    {name}: {result.page_count} page(s), {len(result.warnings)} warning(s)")
    for name, err in failed:
        print(f"  FAIL  {name}: {err}")

    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wpsync")
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="scaffold a new client from the template")
    init_p.add_argument("client")

    list_p = sub.add_parser("list", help="connect and print the page inventory")
    list_p.add_argument("client")

    dump_p = sub.add_parser("dump", help="dump current/** and pages.csv")
    dump_p.add_argument("client", nargs="?")
    dump_p.add_argument("--all", action="store_true", help="dump every client with a profile")

    verify_p = sub.add_parser("verify", help="diff staged/ against a freshly dumped current/")
    verify_p.add_argument("client")

    lint_p = sub.add_parser("lint", help="scan staged/ for leftover Google Docs export artifacts")
    lint_p.add_argument("client")

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            return cmd_init(args.client)
        if args.command == "list":
            return cmd_list(args.client)
        if args.command == "dump":
            if args.all:
                return cmd_dump_all()
            if not args.client:
                parser.error("dump requires a client name, or --all")
            return cmd_dump(args.client)
        if args.command == "verify":
            return cmd_verify(args.client)
        if args.command == "lint":
            return cmd_lint(args.client)
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 1
    except DatabaseError as e:
        print(f"Database error: {e}", file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
