import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import aio_pika
import asyncpg
from aio_pika.abc import AbstractExchange, AbstractIncomingMessage, AbstractQueue
from asyncpg.pool import PoolConnectionProxy

from codeforge.common.contracts import Document as Document

logger = logging.getLogger(__name__)
QUEUE_KEYS = {
    "judge.request": ("judge", ("judge.request",)),
    "judge.result.education": ("judge", ("judge.result.education",)),
    "judge.result.contest": ("judge", ("judge.result.contest",)),
    "education.events": ("events", ("user.*", "contest.finished")),
    "contest.events": ("events", ("user.*",)),
}
type Handler = Callable[[str, Document], Awaitable[None]]


class Broker:
    def __init__(
        self,
        exchanges: dict[str, AbstractExchange],
        queues: dict[str, AbstractQueue],
    ) -> None:
        self.exchanges = exchanges
        self.queues = queues

    async def publish(self, exchange: str, key: str, body: Document) -> None:
        try:
            async with asyncio.timeout(5):
                await self.exchanges[exchange].publish(
                    aio_pika.Message(
                        json.dumps(body).encode(),
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        content_type="application/json",
                    ),
                    routing_key=key,
                    mandatory=True,
                )
        except asyncio.CancelledError as exc:
            # A lost AMQP confirmation may be cancelled independently of the publisher.
            task = asyncio.current_task()
            if task is None or task.cancelling():
                raise
            raise ConnectionError("Broker confirmation interrupted") from exc

    async def consume(self, queue: str, handler: Handler) -> None:
        async def receive(message: AbstractIncomingMessage) -> None:
            try:
                body = json.loads(message.body)
                if not isinstance(body, dict):
                    raise ValueError("Event must be an object")
                await handler(message.routing_key or queue, body)
            except (KeyError, TypeError, ValueError) as exc:
                logger.error("Invalid message in %s: %s", queue, type(exc).__name__)
                await message.reject(requeue=False)
            except Exception as exc:
                logger.warning("Processing %s failed: %s", queue, type(exc).__name__)
                if message.redelivered:
                    await message.reject(requeue=False)
                else:
                    await message.reject(requeue=True)
            else:
                await message.ack()

        await self.queues[queue].consume(receive)


@asynccontextmanager
async def connect(url: str, prefetch: int = 8) -> AsyncIterator[Broker]:
    async with await aio_pika.connect_robust(url) as connection:
        channel = await connection.channel(on_return_raises=True)
        await channel.set_qos(prefetch_count=prefetch)
        exchanges = {
            "events": await channel.declare_exchange("events", "topic", durable=True),
            "judge": await channel.declare_exchange("judge", "direct", durable=True),
        }
        dead = await channel.declare_exchange("dead", "fanout", durable=True)
        quarantine = await channel.declare_queue("dead", durable=True)
        await quarantine.bind(dead)
        queues = {}
        for name, (exchange, keys) in QUEUE_KEYS.items():
            queue = await channel.declare_queue(
                name,
                durable=True,
                arguments={"x-dead-letter-exchange": "dead"},
            )
            for key in keys:
                await queue.bind(exchanges[exchange], key)
            queues[name] = queue
        yield Broker(exchanges, queues)


async def enqueue(conn: PoolConnectionProxy, key: str, body: Document) -> None:
    exchange = "judge" if key.startswith("judge.") else "events"
    await conn.execute(
        "INSERT INTO outbox(exchange, routing_key, body) VALUES($1, $2, $3)",
        exchange,
        key,
        body,
    )


async def publish_pending(
    pool: asyncpg.Pool,
    broker: Broker,
    before_publish: Handler | None = None,
) -> None:
    async with pool.acquire() as conn, conn.transaction():
        rows = await conn.fetch(
            "SELECT * FROM outbox WHERE published_at IS NULL ORDER BY id LIMIT 20 "
            "FOR UPDATE SKIP LOCKED"
        )
        for row in rows:
            if before_publish:
                await before_publish(row["routing_key"], row["body"])
            await broker.publish(row["exchange"], row["routing_key"], row["body"])
            await conn.execute(
                "UPDATE outbox SET published_at=now() WHERE id=$1", row["id"]
            )
