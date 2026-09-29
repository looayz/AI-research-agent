import asyncio

import httpx

TERMINAL = ("completed", "failed", "cancelled")


async def wait_for_research(client: httpx.AsyncClient, research_id: str, timeout: float = 20.0) -> dict:
    """Poll the detail endpoint until the research reaches a terminal status."""
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        detail = (await client.get(f"/api/research/{research_id}")).json()
        if detail["status"] in ("completed", "failed", "cancelled"):
            return detail
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"research still {detail['status']} after {timeout}s")
        await asyncio.sleep(0.05)
