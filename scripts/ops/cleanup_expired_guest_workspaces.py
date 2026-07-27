from __future__ import annotations

import argparse
import json

from argus.domain.guest_cleanup import cleanup_expired_guest_workspaces
from argus.domain.supabase_gateway import SupabaseGateway


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely clean expired anonymous guest workspaces.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=25, choices=range(1, 101))
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = cleanup_expired_guest_workspaces(
        SupabaseGateway.from_env(),
        limit=args.limit,
        dry_run=args.dry_run,
    )
    print(json.dumps(result.as_dict(), sort_keys=True))
    return 1 if result.auth_delete_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
