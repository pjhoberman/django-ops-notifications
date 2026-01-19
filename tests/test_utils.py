"""Tests for block utility functions."""

import pytest

from ops_notifications.utils import (
    context_block,
    divider_block,
    fields_block,
    header_block,
    section_block,
)


class TestBlockUtilities:
    """Tests for standalone block utility functions."""

    def test_header_block(self):
        """header_block should create proper header structure."""
        result = header_block("My Header")
        assert result == {
            "type": "header",
            "text": {"type": "plain_text", "text": "My Header"},
        }

    def test_section_block_markdown(self):
        """section_block should use mrkdwn by default."""
        result = section_block("*Bold* text")
        assert result == {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Bold* text"},
        }

    def test_section_block_plain_text(self):
        """section_block should support plain text."""
        result = section_block("Plain text", markdown=False)
        assert result == {
            "type": "section",
            "text": {"type": "plain_text", "text": "Plain text"},
        }

    def test_divider_block(self):
        """divider_block should create divider."""
        result = divider_block()
        assert result == {"type": "divider"}

    def test_context_block(self):
        """context_block should create context with mrkdwn elements."""
        result = context_block(["Item 1", "Item 2"])
        assert result == {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "Item 1"},
                {"type": "mrkdwn", "text": "Item 2"},
            ],
        }

    def test_context_block_empty(self):
        """context_block should handle empty list."""
        result = context_block([])
        assert result == {"type": "context", "elements": []}

    def test_fields_block(self):
        """fields_block should create section with fields."""
        result = fields_block(["*Label 1:* Value 1", "*Label 2:* Value 2"])
        assert result == {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": "*Label 1:* Value 1"},
                {"type": "mrkdwn", "text": "*Label 2:* Value 2"},
            ],
        }

    def test_fields_block_plain_text(self):
        """fields_block should support plain text."""
        result = fields_block(["Field 1", "Field 2"], markdown=False)
        assert result == {
            "type": "section",
            "fields": [
                {"type": "plain_text", "text": "Field 1"},
                {"type": "plain_text", "text": "Field 2"},
            ],
        }
