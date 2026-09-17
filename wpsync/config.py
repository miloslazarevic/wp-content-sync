"""Profile loading and wp-config.php parsing."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

TABLE_PREFIX_RE = re.compile(r"^[A-Za-z0-9_]+$")

_WP_CONFIG_DEFINE_RE = {
    "DB_NAME": re.compile(r"define\(\s*['\"]DB_NAME['\"]\s*,\s*['\"]([^'\"]*)['\"]\s*\)"),
    "DB_USER": re.compile(r"define\(\s*['\"]DB_USER['\"]\s*,\s*['\"]([^'\"]*)['\"]\s*\)"),
    "DB_PASSWORD": re.compile(r"define\(\s*['\"]DB_PASSWORD['\"]\s*,\s*['\"]([^'\"]*)['\"]\s*\)"),
}
_TABLE_PREFIX_RE = re.compile(r"\$table_prefix\s*=\s*['\"]([^'\"]*)['\"]")


class ConfigError(Exception):
    """Raised for any problem loading or validating a client profile."""


@dataclass
class DatabaseConfig:
    socket: Optional[str]
    host: Optional[str]
    port: Optional[int]
    name: str
    user: str
    password: str
    table_prefix: str


@dataclass
class DumpConfig:
    post_types: List[str] = field(default_factory=lambda: ["page"])
    post_status: List[str] = field(default_factory=lambda: ["publish", "draft"])
    include: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)


@dataclass
class Profile:
    name: str
    label: str
    client_dir: Path
    wp_path: Path
    database: DatabaseConfig
    dump: DumpConfig


def parse_wp_config(wp_config_path: Path) -> dict:
    text = wp_config_path.read_text(encoding="utf-8", errors="replace")

    values = {}
    for key, pattern in _WP_CONFIG_DEFINE_RE.items():
        match = pattern.search(text)
        if match is None:
            raise ConfigError(
                f"{wp_config_path}: could not find a define() for {key}. "
                "Is this a normal WordPress wp-config.php?"
            )
        values[key] = match.group(1)

    prefix_match = _TABLE_PREFIX_RE.search(text)
    if prefix_match is None:
        print(
            f"warning: {wp_config_path}: no $table_prefix found, defaulting to 'wp_'"
        )
        values["table_prefix"] = "wp_"
    else:
        values["table_prefix"] = prefix_match.group(1)

    return values


def load_profile(client_dir: Path) -> Profile:
    profile_path = client_dir / "profile.yml"
    if not profile_path.exists():
        raise ConfigError(f"{profile_path} does not exist")

    with profile_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    name = raw.get("name")
    if not name:
        raise ConfigError(f"{profile_path}: 'name' is required")

    site = raw.get("site") or {}
    wp_path_raw = site.get("wp_path")
    if not wp_path_raw:
        raise ConfigError(f"{profile_path}: 'site.wp_path' is required")

    wp_path = Path(wp_path_raw).expanduser()
    wp_config_path = wp_path / "wp-config.php"
    if not wp_path.exists() or not wp_config_path.exists():
        raise ConfigError(
            f"{profile_path}: site.wp_path '{wp_path}' does not exist or has no "
            "wp-config.php. Is the site path correct and the Local.app site present?"
        )

    parsed = parse_wp_config(wp_config_path)

    db_raw = raw.get("database") or {}
    socket = db_raw.get("socket")
    host = db_raw.get("host")
    port = db_raw.get("port")

    has_socket = bool(socket)
    has_host_port = bool(host) and port is not None
    if has_socket and has_host_port:
        raise ConfigError(
            f"{profile_path}: database config must supply EXACTLY ONE of "
            "socket or host+port, not both"
        )
    if not has_socket and not has_host_port:
        raise ConfigError(
            f"{profile_path}: database config must supply EXACTLY ONE of "
            "socket or host+port"
        )

    database = DatabaseConfig(
        socket=str(Path(socket).expanduser()) if socket else None,
        host=host,
        port=port,
        name=db_raw.get("name") or parsed["DB_NAME"],
        user=db_raw.get("user") or parsed["DB_USER"],
        password=db_raw.get("password") or parsed["DB_PASSWORD"],
        table_prefix=db_raw.get("table_prefix") or parsed["table_prefix"],
    )

    dump_raw = raw.get("dump") or {}
    dump = DumpConfig(
        post_types=dump_raw.get("post_types") or ["page"],
        post_status=dump_raw.get("post_status") or ["publish", "draft"],
        include=dump_raw.get("include") or [],
        exclude=dump_raw.get("exclude") or [],
    )

    return Profile(
        name=name,
        label=raw.get("label") or name,
        client_dir=client_dir,
        wp_path=wp_path,
        database=database,
        dump=dump,
    )
