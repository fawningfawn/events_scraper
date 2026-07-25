"""Subscription matching logic"""


def matches_subscription(event, subscription, event_body=None):
    """
    Check if an event matches a subscription using case-insensitive AND logic.

    - If only title_keyword: matches if found in title
    - If only body_keyword: matches if found in body (checks event.body and event_detail if provided)
    - If both: matches if BOTH are found (AND logic)

    Args:
        event: Event object with title and optional body attributes
        subscription: Subscription object with title_keyword and/or body_keyword
        event_body: Optional body content (can come from EventDetail if event.body is None)

    Returns:
        bool: True if subscription matches event (case-insensitive), False otherwise
    """
    # Handle None inputs
    if event is None or subscription is None:
        return False

    # Get keywords
    title_keyword = (
        subscription.title_keyword.strip()
        if hasattr(subscription, "title_keyword") and subscription.title_keyword
        else None
    )
    body_keyword = (
        subscription.body_keyword.strip()
        if hasattr(subscription, "body_keyword") and subscription.body_keyword
        else None
    )

    # Check if at least one keyword is provided
    if not title_keyword and not body_keyword:
        return False

    # Extract title and body from event
    event_title = None
    if hasattr(event, "title") and event.title:
        event_title = event.title.strip().lower()

    # Use provided event_body, or extract from event.body
    if event_body is None:
        if hasattr(event, "body") and event.body:
            event_body = event.body.strip().lower()
    else:
        event_body = event_body.strip().lower() if event_body else None

    # Title keyword must match if specified
    if title_keyword:
        title_keyword_lower = title_keyword.lower()
        if not event_title or title_keyword_lower not in event_title:
            return False

    # Body keyword must match if specified
    if body_keyword:
        body_keyword_lower = body_keyword.lower()
        if not event_body or body_keyword_lower not in event_body:
            return False

    # All specified keywords matched
    return True
