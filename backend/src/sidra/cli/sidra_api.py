"""Run the API.

Port 8285 by default, from ``PORT_ASSIGNMENTS.md``. Overridable with ``SIDRA_API_PORT``.
"""

from __future__ import annotations

import uvicorn

from sidra.config import get_settings

HOST = "0.0.0.0"  # noqa: S104 - inside the container; the compose file publishes one host port


def main() -> None:  # pragma: no cover - the process entry point
    uvicorn.run("sidra.api.app:create_app", factory=True, host=HOST, port=get_settings().api_port)


if __name__ == "__main__":  # pragma: no cover
    main()
