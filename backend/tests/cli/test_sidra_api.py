from __future__ import annotations

from sidra.cli import sidra_api
from sidra.config import get_settings


def test_the_api_binds_every_interface_inside_the_container() -> None:
    """The compose file publishes exactly one host port; binding to localhost would hide it."""
    assert sidra_api.HOST == "0.0.0.0"  # noqa: S104


def test_the_default_port_is_the_one_the_registry_assigned() -> None:
    assert get_settings().api_port == 8285
