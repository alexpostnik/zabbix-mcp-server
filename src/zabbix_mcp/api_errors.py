#
# Zabbix MCP Server
# Copyright (C) 2026 initMAX s.r.o.
# Licensed under the GNU Affero General Public License v3.
# See LICENSE for details.
#

"""Translate a small allowlist of Zabbix validation facts into safe tool errors."""

import re

from zabbix_utils.exceptions import APIRequestError


API_ERROR_FALLBACK = "Zabbix API call failed. Check server logs for details."

# Neither API error text nor syntactically plausible field names are trusted:
# paths and unexpected/missing keys can themselves contain user data/secrets.
_SAFE_FIELDS = frozenset({
    "actionid", "filter", "evaltype", "formula", "conditions", "formulaid",
    "conditiontype", "operator", "value", "value2", "name", "status", "eventsource",
    "operations", "recovery_operations", "update_operations", "operationtype",
    "hostid", "hostids", "host", "groupid", "groupids", "groups", "templateid",
    "templateids", "templates", "itemid", "itemids", "triggerid", "triggerids",
    "userid", "usrgrpid", "mediatypeid", "interfaceid", "interfaces", "type",
    "output", "selectFilter", "limit", "sortfield", "sortorder", "countOutput",
    "time_from", "time_till", "delay", "key_", "value_type",
})
_PARAMETER_ERROR = re.compile(r'Invalid parameter "(?P<path>/[^"\n]*)": (?P<reason>[^\n]+)\.')
_FIELD_ERROR = re.compile(r'(?:unexpected parameter "(?P<unexpected>[^"]+)"|the parameter "(?P<missing>[^"]+)" is missing)')
_SAFE_REASONS = {
    "cannot be empty": "cannot be empty",
    "an integer is expected": "an integer is expected",
    "a number is expected": "a number is expected",
    "a character string is expected": "a string is expected",
    "an array is expected": "an array is expected",
    "an object is expected": "an object is expected",
    "a boolean is expected": "a boolean is expected",
}


def safe_api_error(error: APIRequestError) -> str:
    """Expose only recognized -32602 validation paths and fixed explanations.

    zabbix-utils APIRequestError has structured code/data attributes. Its
    sibling ProcessingError and all unrecognized errors stay generic; never
    try to recover useful text by echoing or truncating arbitrary exceptions.
    """
    if getattr(error, "code", None) != -32602 or getattr(error, "message", None) != "Invalid params.":
        return API_ERROR_FALLBACK
    data = getattr(error, "data", None)
    if not isinstance(data, str) or len(data) > 512:
        return API_ERROR_FALLBACK
    match = _PARAMETER_ERROR.fullmatch(data)
    if match is None:
        return API_ERROR_FALLBACK
    path = match["path"]
    parts = path[1:].split("/") if path != "/" else []
    if len(parts) > 12 or any(
        part not in _SAFE_FIELDS and re.fullmatch(r"[1-9][0-9]{0,5}", part) is None
        for part in parts
    ):
        return API_ERROR_FALLBACK
    reason = _SAFE_REASONS.get(match["reason"])
    field_error = _FIELD_ERROR.fullmatch(match["reason"])
    if field_error:
        field = field_error["unexpected"] or field_error["missing"]
        if field not in _SAFE_FIELDS:
            return API_ERROR_FALLBACK
        path = path.rstrip("/") + "/" + field
        reason = "unexpected parameter; omit this field" if field_error["unexpected"] else "required parameter is missing"
    if reason is None:
        return API_ERROR_FALLBACK
    return f"Zabbix rejected parameter {path}: {reason}. Check the method's parameter schema."
