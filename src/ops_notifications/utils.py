"""Utility functions for building Slack message blocks.

These standalone functions can be used without the SlackClient instance.
The SlackClient also has these as methods for convenience.
"""

from typing import Any


def header_block(text: str) -> dict[str, Any]:
    """Create a header block.

    Args:
        text: The header text (plain text only).

    Returns:
        A Slack header block.
    """
    return {"type": "header", "text": {"type": "plain_text", "text": text}}


def section_block(text: str, markdown: bool = True) -> dict[str, Any]:  # noqa: FBT001, FBT002
    """Create a section block.

    Args:
        text: The section content.
        markdown: Whether to render as markdown (default True).

    Returns:
        A Slack section block.
    """
    return {
        "type": "section",
        "text": {
            "type": "mrkdwn" if markdown else "plain_text",
            "text": text,
        },
    }


def divider_block() -> dict[str, Any]:
    """Create a divider block.

    Returns:
        A Slack divider block.
    """
    return {"type": "divider"}


def context_block(elements: list[str]) -> dict[str, Any]:
    """Create a context block with mrkdwn elements.

    Args:
        elements: List of markdown-formatted strings.

    Returns:
        A Slack context block.
    """
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": element} for element in elements],
    }


def fields_block(fields: list[str], markdown: bool = True) -> dict[str, Any]:  # noqa: FBT001, FBT002
    """Create a section block with fields (2-column layout).

    Args:
        fields: List of field text values.
        markdown: Whether to render fields as markdown (default True).

    Returns:
        A Slack section block with fields.
    """
    return {
        "type": "section",
        "fields": [
            {"type": "mrkdwn" if markdown else "plain_text", "text": field}
            for field in fields
        ],
    }
