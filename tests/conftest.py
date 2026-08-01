"""Shared test fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Let Home Assistant load this custom integration in every test."""
    return None
