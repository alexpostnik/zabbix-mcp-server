#
# Zabbix MCP Server
# Copyright (C) 2026 initMAX s.r.o.
# Licensed under the GNU Affero General Public License v3.
# See LICENSE for details.
#

"""Describe and validate the action filter's evaluation-mode contract.

Event-source-specific conditions and operations remain Zabbix's responsibility.
See CAction::getFilterValidationRules in Zabbix 7.0 and 7.4.
"""

from typing import Any


ACTION_FILTER_DESCRIPTION = (
    "filter.evaltype: 0=And/Or, 1=And, 2=Or, 3=custom expression. "
    "For evaltype 0/1/2 omit filter.formula and every condition.formulaid, "
    "including when copying a filter returned by action_get. "
    "For evaltype=3 supply formula and conditions with unique uppercase formulaid "
    "labels referenced by the expression. An omitted filter leaves it unchanged on update."
)

ACTION_FILTER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": ACTION_FILTER_DESCRIPTION,
    "required": ["evaltype"],
    "additionalProperties": True,
    "properties": {
        "evaltype": {
            "type": ["integer", "string"],
            "enum": [0, 1, 2, 3, "0", "1", "2", "3"],
            "description": "0=And/Or, 1=And, 2=Or, 3=custom expression.",
        },
        "formula": {
            "type": "string",
            "description": "Required only for evaltype=3; omit for 0/1/2. Example: A and (B or C).",
        },
        "conditions": {
            "type": "array",
            "description": "Filter conditions. Required for evaltype=3; may be empty for 0/1/2.",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "conditiontype": {
                        "type": ["integer", "string"],
                        "description": "Condition type allowed by the action's eventsource.",
                    },
                    "operator": {
                        "type": ["integer", "string"],
                        "description": "Comparison operator allowed for this conditiontype.",
                    },
                    "value": {
                        "type": ["string", "integer"],
                        "description": "Comparison value or object ID, when required by conditiontype.",
                    },
                    "value2": {
                        "type": "string",
                        "description": "Secondary value, only for condition types that support it.",
                    },
                    "formulaid": {
                        "type": "string",
                        "description": "Required only for evaltype=3; omit for 0/1/2. Unique uppercase label, e.g. A.",
                    },
                },
            },
        },
    },
}


class ActionFilterError(ValueError):
    """A local validation error containing only fixed field paths and guidance."""


def validate_action_filter(method: str, params: Any) -> None:
    """Reject incompatible action filter fields without changing the payload.

    Run after local authorization but before version/time-zone lookups, which
    may contact the backend. Unknown fields and condition semantics are left
    to Zabbix so this is not a closed, version-specific action schema.
    """
    if method.lower() not in ("action.create", "action.update"):
        return
    if not isinstance(params, dict) or "filter" not in params:
        return
    action_filter = params["filter"]
    if not isinstance(action_filter, dict):
        raise ActionFilterError("params.filter: an object is required.")
    if "evaltype" not in action_filter:
        raise ActionFilterError("params.filter.evaltype: required when supplying filter.")
    mode = action_filter["evaltype"]
    if type(mode) not in (int, str) or mode not in (0, 1, 2, 3, "0", "1", "2", "3"):
        raise ActionFilterError("params.filter.evaltype: use 0, 1, 2, 3 (integer or numeric string).")
    custom = str(mode) == "3"
    if not custom and "formula" in action_filter:
        raise ActionFilterError("params.filter.formula: only allowed with evaltype=3; omit it for 0/1/2.")
    if custom and "formula" not in action_filter:
        raise ActionFilterError("params.filter.formula: required for evaltype=3.")
    if custom and "conditions" not in action_filter:
        raise ActionFilterError("params.filter.conditions: required for evaltype=3.")
    conditions = action_filter.get("conditions", [])
    if not isinstance(conditions, list):
        raise ActionFilterError("params.filter.conditions: an array is required.")
    for index, condition in enumerate(conditions):
        path = f"params.filter.conditions[{index}]"
        if not isinstance(condition, dict):
            raise ActionFilterError(f"{path}: an object is required.")
        if not custom and "formulaid" in condition:
            raise ActionFilterError(
                f"{path}.formulaid: only allowed with evaltype=3; omit it for 0/1/2."
            )
        if custom and "formulaid" not in condition:
            raise ActionFilterError(f"{path}.formulaid: required for evaltype=3.")
