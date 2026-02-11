# Copyright (c) 2024-2025 Gary Kuepper
# Licensed under the MIT License.

import datetime


def get_age_str(captured_at: datetime.datetime | None) -> str:
    """Returns a human-readable age string for a timestamp."""
    if not captured_at:
        return "unknown"

    # Ensure captured_at is offset-aware UTC if it isn't
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=datetime.timezone.utc)

    now = datetime.datetime.now(datetime.timezone.utc)
    diff = now - captured_at
    seconds = int(diff.total_seconds())

    if seconds < 0:
        return "just now"
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"
