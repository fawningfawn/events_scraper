"""Event deduplication utilities"""

import hashlib
from typing import Optional


def compute_content_hash(
    title: Optional[str], location: Optional[str], time: Optional[str]
) -> str:
    """
    Compute content hash for deduplication.

    Hash is computed from title + location + time, normalized for consistency.
    NULL/None values are treated as empty strings.

    Args:
        title: Event title (or None)
        location: Event location (or None)
        time: Event time (HH:MM format), or None for all-day events

    Returns:
        32-character hex string (MD5 hash)
    """
    # Normalize: strip whitespace, collapse internal whitespace, lowercase, handle None values
    normalized_title = " ".join(str(title or "").strip().split()).lower()
    normalized_location = " ".join(str(location or "").strip().split()).lower()
    normalized_time = str(time or "").strip()

    # Combine for hash
    content = f"{normalized_title}|{normalized_location}|{normalized_time}"

    # Return MD5 hash as hex
    return hashlib.md5(content.encode()).hexdigest()
