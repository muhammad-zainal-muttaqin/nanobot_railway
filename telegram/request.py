from __future__ import annotations

from typing import Any

import httpx


class HTTPXRequest(httpx.AsyncClient):
    """PTB-compatible request adapter backed by httpx.AsyncClient."""

    def __init__(
        self,
        connection_pool_size: int | None = None,
        pool_timeout: float | None = None,
        connect_timeout: float | None = None,
        read_timeout: float | None = None,
        write_timeout: float | None = None,
        proxy: str | None = None,
        **kwargs: Any,
    ):
        limits = kwargs.pop("limits", None)
        if limits is None and connection_pool_size is not None:
            limits = httpx.Limits(
                max_connections=connection_pool_size,
                max_keepalive_connections=connection_pool_size,
            )

        timeout = kwargs.pop("timeout", None)
        if timeout is None:
            timeout = httpx.Timeout(
                timeout=read_timeout or 30.0,
                connect=connect_timeout or 15.0,
                read=read_timeout or 30.0,
                write=write_timeout or 30.0,
                pool=pool_timeout or 5.0,
            )

        super().__init__(timeout=timeout, limits=limits, proxy=proxy, **kwargs)

__all__ = ["HTTPXRequest"]
