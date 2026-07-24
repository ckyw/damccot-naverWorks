from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.secret_manager import read_secret


@dataclass(frozen=True)
class Settings:
    access_token: str
    refresh_token: str
    client_id: str
    client_secret: str
    token_url: str
    token_refresh_leeway_seconds: int
    refresh_token_secret_resource: str
    sharedrive_id: str
    root_file_id: str | None
    output_dir: Path
    max_depth: int | None
    collection_mode: str
    request_sleep_seconds: float
    log_level: str


def _optional_int(value: str | int | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect Naver Works Shared Drive folder/file tree metadata."
    )
    parser.add_argument("--max-depth", type=int, default=None)
    parser.add_argument("--sharedrive-id", default=None)
    parser.add_argument("--root-file-id", default=None)
    parser.add_argument("--client-id", default=None)
    parser.add_argument("--gcp-project", default=None)
    parser.add_argument("--client-secret-name", default=None)
    parser.add_argument("--refresh-token-name", default=None)
    parser.add_argument(
        "--full-depth",
        action="store_true",
        help="Collect all descendant levels, ignoring MAX_DEPTH.",
    )
    parser.add_argument("--mode", default=None)
    parser.add_argument("--output-dir", default=None)
    return parser


def load_settings(args: argparse.Namespace | None = None) -> Settings:
    load_dotenv()
    args = args or argparse.Namespace(
        max_depth=None,
        full_depth=False,
        mode=None,
        output_dir=None,
        sharedrive_id=None,
        root_file_id=None,
        client_id=None,
        gcp_project=None,
        client_secret_name=None,
        refresh_token_name=None,
    )

    access_token = os.getenv("NAVER_WORKS_ACCESS_TOKEN", "").strip()
    refresh_token = os.getenv("NAVER_WORKS_REFRESH_TOKEN", "").strip()
    client_id = (args.client_id or os.getenv("NAVER_WORKS_CLIENT_ID", "")).strip()
    client_secret = os.getenv("NAVER_WORKS_CLIENT_SECRET", "").strip()
    token_url = os.getenv(
        "NAVER_WORKS_TOKEN_URL", "https://auth.worksmobile.com/oauth2/v2.0/token"
    ).strip()
    sharedrive_id = (args.sharedrive_id or os.getenv("NAVER_WORKS_SHARED_DRIVE_ID", "")).strip()
    root_file_id = (
        args.root_file_id
        if args.root_file_id is not None
        else os.getenv("NAVER_WORKS_ROOT_FILE_ID", "").strip()
    ) or None
    gcp_project = (args.gcp_project or "").strip()
    client_secret_name = (args.client_secret_name or "").strip()
    refresh_token_name = (args.refresh_token_name or "").strip()

    if client_secret_name or refresh_token_name:
        if not gcp_project:
            raise ValueError("--gcp-project is required when reading Secret Manager values.")
        if not client_secret_name or not refresh_token_name:
            raise ValueError(
                "Provide both --client-secret-name and --refresh-token-name."
            )
        try:
            client_secret = read_secret(gcp_project, client_secret_name).strip()
            refresh_token = read_secret(gcp_project, refresh_token_name).strip()
        except Exception as exc:
            raise ValueError(f"Could not read Secret Manager values: {exc}") from exc

    missing = [
        name
        for name, value in {
            "NAVER_WORKS_SHARED_DRIVE_ID": sharedrive_id,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    if not access_token and not refresh_token:
        raise ValueError(
            "Set NAVER_WORKS_ACCESS_TOKEN or NAVER_WORKS_REFRESH_TOKEN."
        )

    max_depth = None if getattr(args, "full_depth", False) else args.max_depth
    if max_depth is None and not getattr(args, "full_depth", False):
        max_depth = _optional_int(os.getenv("MAX_DEPTH"))

    output_dir = Path(
        args.output_dir or os.getenv("OUTPUT_DIR", "./data/sources/default")
    )

    return Settings(
        access_token=access_token,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_url=token_url,
        token_refresh_leeway_seconds=_optional_int(
            os.getenv("NAVER_WORKS_TOKEN_REFRESH_LEEWAY_SECONDS", "300")
        )
        or 300,
        refresh_token_secret_resource=(
            f"projects/{gcp_project}/secrets/{refresh_token_name}"
            if gcp_project and refresh_token_name
            else os.getenv("NAVER_WORKS_REFRESH_TOKEN_SECRET_RESOURCE", "").strip()
        ),
        sharedrive_id=sharedrive_id,
        root_file_id=root_file_id,
        output_dir=output_dir,
        max_depth=max_depth,
        collection_mode=args.mode or os.getenv("COLLECTION_MODE", "full"),
        request_sleep_seconds=float(os.getenv("REQUEST_SLEEP_SECONDS", "0.2")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
