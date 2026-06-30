"""Schema registry + compatibility governance (DATA-2). Blueprint Part 28.2, 32.1."""
from data.registry.schema_registry import (  # noqa: F401
    SchemaRegistry,
    Compatibility,
    is_compatible,
    register_l0,
)
