"""
Utility functions for the OPC UA connector.
"""

import re
from typing import Any


def clean_node_id(node_id: str) -> str:
    """Clean ExpandedNodeId representation to a parseable string format.

    :param node_id: Raw node ID string (may contain ExpandedNodeId format).
    :return: Cleaned node ID string (e.g. 'ns=2;s=Pump01' or 'ns=0;i=85').
    """
    if "ExpandedNodeId" in node_id:
        ns_match = re.search(r"NamespaceIndex=(\d+)", node_id)
        id_match = re.search(r"Identifier=([^,\)]+)", node_id)
        if ns_match and id_match:
            ns = ns_match.group(1)
            ident = id_match.group(1).strip("'\"")
            if ident.isdigit():
                return f"ns={ns};i={ident}"
            else:
                return f"ns={ns};s={ident}"
    return node_id


def to_json_safe(val: Any) -> Any:
    """Convert custom OPC UA objects, datetimes, bytes, or variants into JSON-serializable primitives.

    :param val: Input payload or data object.
    :return: Standard JSON primitive (int, float, str, bool, list, dict, or None).
    """
    if val is None or isinstance(val, (int, float, str, bool)):
        return val
    if isinstance(val, (list, tuple)):
        return [to_json_safe(item) for item in val]
    if isinstance(val, dict):
        return {str(k): to_json_safe(v) for k, v in val.items()}
    return str(val)


# Aliases for backward compatibility
_clean_node_id = clean_node_id
_to_json_safe = to_json_safe

