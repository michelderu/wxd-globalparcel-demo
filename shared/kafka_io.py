"""Tiny JSON Kafka helpers for Apache Kafka."""

from __future__ import annotations

import json
import time
from typing import Any

from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import NoBrokersAvailable, TopicAlreadyExistsError

from shared.config import KAFKA_BOOTSTRAP


def json_dumps(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def json_loads(raw: bytes | None) -> dict[str, Any]:
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _wait_for_broker(bootstrap: str, attempts: int = 20) -> None:
    last: Exception | None = None
    for _ in range(attempts):
        try:
            client = KafkaProducer(bootstrap_servers=bootstrap, request_timeout_ms=4000)
            client.close()
            return
        except Exception as exc:
            last = exc
            time.sleep(1)
    raise last or NoBrokersAvailable()


def producer(bootstrap: str = KAFKA_BOOTSTRAP) -> KafkaProducer:
    _wait_for_broker(bootstrap)
    return KafkaProducer(
        bootstrap_servers=bootstrap,
        value_serializer=json_dumps,
        key_serializer=lambda k: k.encode("utf-8") if isinstance(k, str) else k,
        linger_ms=20,
        acks="all",
    )


def consumer(
    topic: str | list[str],
    group_id: str,
    *,
    bootstrap: str = KAFKA_BOOTSTRAP,
    auto_offset_reset: str = "earliest",
) -> KafkaConsumer:
    _wait_for_broker(bootstrap)
    return KafkaConsumer(
        *([topic] if isinstance(topic, str) else topic),
        bootstrap_servers=bootstrap,
        group_id=group_id,
        value_deserializer=json_loads,
        key_deserializer=lambda k: k.decode("utf-8") if k else None,
        auto_offset_reset=auto_offset_reset,
        enable_auto_commit=True,
    )


def ensure_topics(topics: dict[str, dict[str, str]], bootstrap: str = KAFKA_BOOTSTRAP) -> None:
    _wait_for_broker(bootstrap)
    admin = KafkaAdminClient(bootstrap_servers=bootstrap, client_id="streamhouse-admin")
    try:
        new_topics = [
            NewTopic(name=name, num_partitions=1, replication_factor=1, topic_configs=configs)
            for name, configs in topics.items()
        ]
        admin.create_topics(new_topics, validate_only=False)
    except TopicAlreadyExistsError:
        pass
    except Exception as exc:
        message = str(exc).lower()
        if "already exists" not in message and "topicexists" not in message:
            raise
    finally:
        admin.close()
