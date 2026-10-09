"""Platform connectors: honest import/export with a capability matrix."""
from forge.connect.registry import (
    BaseConnector,
    capabilities_table,
    get_connector,
    list_connectors,
)

__all__ = ["BaseConnector", "capabilities_table", "get_connector",
           "list_connectors"]
