import asyncio
from uuid import UUID

stock_queue: asyncio.Queue[UUID] = asyncio.Queue()
transport_queue: asyncio.Queue[UUID] = asyncio.Queue()