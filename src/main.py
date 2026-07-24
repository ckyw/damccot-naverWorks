from __future__ import annotations

import sys

from src.batcher import write_batches
from src.collector import collect_drive_tree
from src.config import build_parser, load_settings
from src.reporter import write_reports
from src.secret_manager import RefreshTokenSecretStore
from src.token_provider import NaverWorksTokenProvider
from src.tree_exports import write_tree_exports
from src.utils import configure_logging, ensure_output_dirs, utc_now_iso, write_json


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        settings = load_settings(args)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    configure_logging(settings.log_level)
    ensure_output_dirs(settings.output_dir)
    refresh_token_store = (
        RefreshTokenSecretStore(settings.refresh_token_secret_resource)
        if settings.refresh_token_secret_resource
        else None
    )
    token_provider = NaverWorksTokenProvider(
        access_token=settings.access_token,
        refresh_token=settings.refresh_token,
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        token_url=settings.token_url,
        refresh_leeway_seconds=settings.token_refresh_leeway_seconds,
        persist_rotated_refresh_token=(refresh_token_store.persist if refresh_token_store else None),
    )

    items = collect_drive_tree(
        settings.sharedrive_id,
        settings.root_file_id,
        token_provider,
        settings.max_depth,
        request_sleep_seconds=settings.request_sleep_seconds,
    )
    raw_payload = {
        "collectedAt": utc_now_iso(),
        "sharedriveId": settings.sharedrive_id,
        "rootFileId": settings.root_file_id,
        "totalItems": len(items),
        "items": items,
    }
    write_json(settings.output_dir / "raw" / "sharedrive_tree_raw.json", raw_payload)
    write_tree_exports(items, settings.output_dir)
    write_reports(items, settings.output_dir)
    write_batches(items, settings.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
