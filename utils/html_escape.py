"""
HTML Escaping Utilities for Telegram HTML Mode

Prevents HTML injection attacks by escaping user-controllable data
before embedding in HTML-formatted messages.

Security Note:
- ALWAYS use safe_html() for user-provided data (usernames, addresses, custom text)
- NEVER escape localized/static text or pre-formatted HTML
- Escapes: < > & " ' to prevent tag injection and attribute breakout
"""

import html
from typing import Optional


def safe_html(text: Optional[str]) -> str:
    """
    Escapes HTML special characters in user-provided text.

    Prevents injection attacks when embedding user data in Telegram HTML messages.

    Args:
        text: User-provided string (username, address, custom message, etc.)

    Returns:
        HTML-escaped string safe to embed in HTML

    Examples:
        >>> safe_html("TestUser</b><script>alert(1)</script>")
        "TestUser&lt;/b&gt;&lt;script&gt;alert(1)&lt;/script&gt;"

        >>> safe_html("User<123>")
        "User&lt;123&gt;"

        >>> safe_html(None)
        ""
    """
    if text is None:
        return ""
    return html.escape(str(text), quote=True)


def safe_url(url: Optional[str]) -> str:
    """
    Sanitizes URLs for use in Telegram HTML <a> tags.

    Basic validation to prevent javascript: and data: URI injection.

    Args:
        url: User-provided URL

    Returns:
        Sanitized URL or empty string if invalid

    Examples:
        >>> safe_url("https://t.me/user123")
        "https://t.me/user123"

        >>> safe_url("javascript:alert(1)")
        ""
    """
    if not url:
        return ""

    url_str = str(url).strip()

    # Only allow safe protocols
    safe_protocols = ["http://", "https://", "tg://", "t.me/"]
    if not any(url_str.startswith(proto) for proto in safe_protocols):
        return ""

    return html.escape(url_str, quote=True)
