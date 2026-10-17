# Action filter validation and API error feedback

The action tools now describe `params.filter` in `tools/list`, and reject
incompatible evaluation modes before a backend request. This addresses the
action-filter portion of overly generic write-tool schemas; it does not define
complete schemas for every Zabbix method.

For example, to require a host-group condition using And:

```json
{
  "params": {
    "actionid": "123",
    "filter": {
      "evaltype": 1,
      "conditions": [{"conditiontype": 0, "operator": 0, "value": "456"}]
    }
  }
}
```

For a custom expression, use `evaltype=3`, supply `formula`, and assign each
condition an uppercase `formulaid` referenced by that expression. For example:

```json
{
  "params": {
    "actionid": "123",
    "filter": {
      "evaltype": 3,
      "formula": "A",
      "conditions": [{"conditiontype": 0, "value": "456", "formulaid": "A"}]
    }
  }
}
```

The MCP server does not silently discard invalid fields. With `evaltype=1`, a
condition containing `formulaid` returns an error at
`params.filter.conditions[0].formulaid`, explaining that it is only allowed
with `evaltype=3`. Status-only updates continue to omit `filter` entirely.
For modes 0/1/2, empty conditions and omitted conditions are accepted locally.

## Boundaries

- Local token authorization and server read-only checks still run first.
- Validation runs for dedicated action tools, `zabbix_raw_api_call`,
  `action_prepare`, and `action_confirm`. Valid payloads are not rewritten by
  this check. Existing parameter normalization still applies to dedicated tools.
- The schema is open to other action/condition properties. It documents the
  common filter fields; Zabbix remains responsible for expression syntax,
  unique labels, event-source-specific conditions, operations, and permissions.
- Structured `zabbix_utils.APIRequestError` errors with code `-32602` expose
  only recognized field names, bounded array indexes, and fixed validation
  reasons. Missing/unexpected fields, empty values, and common type errors are
  supported. Other `APIRequestError` responses and plain `ProcessingError`
  failures stay generic. Existing `ValueError` handling in dedicated/raw tools
  is outside this change's scope.
  Raw backend text is retained in server logs, not returned in these tool errors.
- This does not diagnose or fix network timeouts or action delivery delays.

The filter rules were checked against Zabbix's `getFilterValidationRules` in
[6.0](https://github.com/zabbix/zabbix/blob/release/6.0/ui/include/classes/api/services/CAction.php),
[7.0.29](https://github.com/zabbix/zabbix/blob/7.0.29/ui/include/classes/api/services/CAction.php),
and [7.4](https://github.com/zabbix/zabbix/blob/release/7.4/ui/include/classes/api/services/CAction.php).
Unlike the simplified action-object documentation table, these implementations
require `conditions` only for custom expressions.

## TDD evidence

Journeys were derived from the reported invalid action filter and generic error
response: discover a usable filter contract, reject a bad request without a
backend write, preserve valid actions, and return actionable errors safely.

`python -m pytest tests/test_action_filter_contract.py -q` was run before and
after implementation. RED reproduced missing nested schema, missing local
rejection, hidden safe API errors, and arbitrary exception text exposed by
`action_confirm`: 51 failures (including subtests), 10 passes, 40 subtest passes.
GREEN passed the same target: 11 tests and 90 subtests.

| Guarantee | Test type | Evidence |
| --- | --- | --- |
| Formula fields are rejected for modes 0/1/2 before version lookup or write | Registered-tool integration | `test_formulaid_rejected_for_non_expression_modes_on_all_entry_points` |
| Omitted filters, empty conditions, custom expressions, unknown properties and inputs are preserved | Registered-tool integration | `test_valid_action_payloads_and_unknown_properties_are_preserved` |
| Local authorization and rate limits remain effective | Registered-tool integration | Authorization and rate-limit tests |
| Known validation reasons are visible; arbitrary backend text stays hidden | Registered-tool integration | Safe/unsafe API error tests across dedicated, raw and confirm paths |
| Published schema and `isError=true` reach an MCP client | In-memory MCP protocol | `test_protocol_publishes_filter_schema_and_is_error_results` |

These are local MCP code tests using a fake Zabbix backend, not evidence of a
production Zabbix configuration change. The optional LLM integration script
`scripts/test_with_llm.py` is outside this suite and requires separate SDK and
credentials.

Focused branch coverage was measured with
`python -m coverage run --branch --source=zabbix_mcp.api.action_filter,zabbix_mcp.api_errors -m pytest tests/test_action_filter_contract.py -q`
and `python -m coverage report -m`: **100%** for both new modules (66 statements
and 40 branches combined). Compilation of all five changed Python modules also
passed. No formatter or security-scanner packages were installed for this change.

The full repository test directory passed under branch coverage:
`python -m coverage run --branch -m pytest tests -q` — **654 tests and 194 subtests
passed**. The first sandboxed run passed 638 tests but blocked 16 HTTP test
setups from binding loopback ports; the complete rerun with local socket access
passed without skips. Bare `pytest` also collects the optional LLM script above,
so `tests` is the bounded suite used here.
