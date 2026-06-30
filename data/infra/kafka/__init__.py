"""Kafka topic definitions + producer/consumer client wrappers (DATA-3)."""
from data.infra.kafka.topics import (  # noqa: F401
    TOPIC_DEFS,
    TopicDef,
    all_topics,
    partition_for,
    PARTITIONING_POLICY,
)
from data.infra.kafka.clients import (  # noqa: F401
    Producer,
    Consumer,
    make_producer,
    make_consumer,
)
