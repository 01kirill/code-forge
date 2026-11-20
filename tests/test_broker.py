import asyncio
from functools import partial
from unittest.mock import AsyncMock

import pytest
from aio_pika.abc import AbstractExchange
from codeforge.common.broker import Broker
from codeforge.common.runtime import recurring


async def test_cancelled_transport_confirmation_is_retryable() -> None:
    exchange = AsyncMock(spec=AbstractExchange)
    exchange.publish.side_effect = asyncio.CancelledError
    broker = Broker({"judge": exchange}, {})

    with pytest.raises(ConnectionError, match="confirmation interrupted"):
        await broker.publish("judge", "judge.request", {"id": "sample"})

    exchange.publish.side_effect = None
    await broker.publish("judge", "judge.request", {"id": "sample"})
    assert exchange.publish.await_count == 2


async def test_publisher_honors_explicit_shutdown_cancellation() -> None:
    exchange = AsyncMock(spec=AbstractExchange)
    entered = asyncio.Event()

    async def waiting() -> None:
        entered.set()
        await asyncio.Event().wait()

    async def pending(*args: object, **kwargs: object) -> None:
        await waiting()

    exchange.publish.side_effect = pending
    broker = Broker({"judge": exchange}, {})
    task = asyncio.create_task(broker.publish("judge", "judge.request", {}))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_background_publisher_retries_after_one_failure() -> None:
    called = 0
    recovered = asyncio.Event()

    async def publish(marker: asyncio.Event) -> None:
        nonlocal called
        called += 1
        if called == 1:
            raise ConnectionError("Broker restarted")
        marker.set()

    async with recurring(partial(publish, recovered)):
        async with asyncio.timeout(2):
            await recovered.wait()

    assert called == 2
