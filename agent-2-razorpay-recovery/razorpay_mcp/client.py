"""Razorpay MCP client — connects to the remote MCP server with Basic auth."""
import base64
import os
import time
from typing import Any

import structlog
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = structlog.get_logger()


class RazorpayMCPError(Exception):
    """Raised when an MCP tool call fails.

    Carries an HTTP status code so callers can decide whether to retry.
    401 and 400 are not retryable — everything else potentially is.
    """

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


class RazorpayMCPClient:
    """Async context manager for the Razorpay remote MCP server.

    Usage:
        async with RazorpayMCPClient(key_id, key_secret) as client:
            result = await client.call_tool("fetch_all_payments", {...})

    Wraps the MCP transport so callers never deal with connection lifecycle —
    the context manager guarantees clean teardown even on errors.
    """

    MCP_URL = "https://mcp.razorpay.com/mcp"

    def __init__(self, key_id: str, key_secret: str) -> None:
        auth = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
        self._headers = {"Authorization": f"Basic {auth}"}
        self._session: ClientSession | None = None
        self._transport_ctx: Any = None

    async def __aenter__(self) -> "RazorpayMCPClient":
        # Streamable HTTP is the current MCP transport standard for remote servers
        self._transport_ctx = streamablehttp_client(
            self.MCP_URL, headers=self._headers
        )
        read, write, _ = await self._transport_ctx.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        logger.info("razorpay_mcp_connected", url=self.MCP_URL)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._session:
            await self._session.__aexit__(*args)
        if self._transport_ctx:
            await self._transport_ctx.__aexit__(*args)
        logger.info("razorpay_mcp_disconnected")

    async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
        """Call a Razorpay MCP tool and log every call with timing.

        All tool calls are centralised here so logging, timing, and error
        normalisation happen in one place rather than scattered across callers.
        """
        if not self._session:
            raise RuntimeError("Client not connected — use as async context manager")

        start_ms = int(time.time() * 1000)
        try:
            result = await self._session.call_tool(name, args)
            duration_ms = int(time.time() * 1000) - start_ms
            logger.info(
                "mcp_tool_call",
                tool=name,
                params=args,
                duration_ms=duration_ms,
            )
            return result
        except Exception as e:
            duration_ms = int(time.time() * 1000) - start_ms
            logger.error(
                "mcp_tool_error",
                tool=name,
                params=args,
                error=str(e),
                duration_ms=duration_ms,
            )
            raise RazorpayMCPError(str(e)) from e


def get_client() -> RazorpayMCPClient:
    """Create a client from environment variables."""
    return RazorpayMCPClient(
        key_id=os.environ["RAZORPAY_KEY_ID"],
        key_secret=os.environ["RAZORPAY_KEY_SECRET"],
    )
