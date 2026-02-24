"""Sanity checks for exported paper data.

This module reads a JSON config describing conditional rules and validates a single
paper export entry against those rules.

Config format (JSON): a list of rule objects, each with at least `when` and `then`.

Example rule:
{
  "id": "example",
  "when": {"source": "response", "question": "Q1", "attribute": "value", "equals": "test"},
  "then": {"source": "response", "question": "Q1", "attribute": "value2", "must_equal": "test3"},
  "message": "value2 must be test3 when value is test"
}

Supported operators in `when`: equals (string or boolean).
Supported assertions in `then`: must_equal (string), must_not_equal (string).

The validator is intentionally small and dependency-free so it can be shipped
without extra packages.
"""

from __future__ import annotations

import json
from typing import Dict, List, Any, Optional


def _load_config(config_path: str) -> List[Dict[str, Any]]:
    try:
        with open(config_path, 'r') as f:
            data = json.load(f)
            # Accept either a dict with 'rules' key or a raw list
            if isinstance(data, dict) and 'rules' in data:
                return data['rules']
            if isinstance(data, list):
                return data
    except Exception:
        return []
    return []


def _get_response_values(paper_entry: Dict[str, Any], question: str, attribute: str) -> List[str]:
    responses = paper_entry.get('responses', {})
    q = responses.get(question, {})
    vals = q.get(attribute, [])
    if not isinstance(vals, list):
        return []
    return vals


def _get_toggle_enabled(paper_entry: Dict[str, Any], question: str, attribute: str) -> bool:
    toggles = paper_entry.get('toggle_states', {})
    q = toggles.get(question, {})
    a = q.get(attribute, {})
    if isinstance(a, dict):
        return bool(a.get('enabled', False))
    # legacy or absent -> False
    return False


def _matches_value_in_list(values: List[str], expected: Any) -> bool:
    """Return True if expected matches any entry in values.

    Matching allows exact string match or entries with prefixes like "Other: ..." or "Discussion needed: ...".
    For example, expected=="Other" will match "Other: foo".
    """
    # Booleans are not matched here
    if isinstance(expected, bool):
        return False

    def _normalize_text(s: str) -> str:
        # Lowercase, strip whitespace, replace common punctuation with space
        return ''.join(ch.lower() if ch.isalnum() or ch.isspace() else ' ' for ch in s).strip()

    norm_expected = None
    if isinstance(expected, str):
        norm_expected = _normalize_text(expected)

    for v in values:
        # Exact match for non-strings (unlikely) or string compare
        if v == expected:
            return True

        if isinstance(v, str):
            # If v is in "Prefix: detail" form, compare the prefix too
            if ':' in v:
                prefix, _rest = v.split(':', 1)
                if norm_expected is not None and _normalize_text(prefix) == norm_expected:
                    return True

            # Normalize both sides and compare
            if norm_expected is not None and _normalize_text(v) == norm_expected:
                return True

    return False


def validate_paper(paper_entry: Dict[str, Any], config_path: str = 'sanity_checks.json') -> List[str]:
    """Validate a single paper export entry against rules in config_path.

    Returns a list of human-readable violation messages (empty when all pass).
    """
    rules = _load_config(config_path)
    violations: List[str] = []

    for rule in rules:
        when = rule.get('when', {})
        then = rule.get('then', {})
        message = rule.get('message', None)

        # Evaluate `when` condition
        src = when.get('source', 'response')
        q = when.get('question')
        a = when.get('attribute')

        if src == 'toggle':
            if q is None or a is None:
                continue
            actual = _get_toggle_enabled(paper_entry, q, a)
            # 'equals' can be boolean
            if 'equals' in when:
                expected = bool(when['equals'])
                condition_met = (actual == expected)
            else:
                # no supported operator -> skip
                condition_met = False
        else:  # response (default)
            if q is None or a is None:
                continue
            values = _get_response_values(paper_entry, q, a)
            if 'equals' in when:
                expected = when['equals']
                condition_met = _matches_value_in_list(values, expected)
            else:
                condition_met = False

        if not condition_met:
            # when not met -> rule not applicable
            continue

        # Evaluate `then` assertions
        t_src = then.get('source', 'response')
        t_q = then.get('question')
        t_a = then.get('attribute')

        if t_src == 'toggle':
            if t_q is None or t_a is None:
                continue
            actual = _get_toggle_enabled(paper_entry, t_q, t_a)
            if 'must_equal' in then:
                expected = bool(then['must_equal'])
                ok = (actual == expected)
            elif 'must_not_equal' in then:
                expected = bool(then['must_not_equal'])
                ok = (actual != expected)
            else:
                ok = True
        else:
            if t_q is None or t_a is None:
                continue
            target_values = _get_response_values(paper_entry, t_q, t_a)
            if 'must_equal' in then:
                expected = then['must_equal']
                ok = _matches_value_in_list(target_values, expected)
            elif 'must_not_equal' in then:
                expected = then['must_not_equal']
                ok = not _matches_value_in_list(target_values, expected)
            else:
                ok = True

        if not ok:
            if message:
                violations.append(message)
            else:
                violations.append(f"Rule '{rule.get('id', '<unknown>')}' violated")

    return violations


if __name__ == '__main__':
    # Simple manual test helper
    import sys
    if len(sys.argv) < 2:
        print('Usage: sanity_checks.py <exported_paper_json> [config.json]')
        sys.exit(2)
    paper_path = sys.argv[1]
    cfg = sys.argv[2] if len(sys.argv) > 2 else 'sanity_checks.json'
    try:
        with open(paper_path, 'r') as f:
            paper = json.load(f)
    except Exception as e:
        print('Error loading paper file:', e)
        sys.exit(2)
    v = validate_paper(paper, cfg)
    if v:
        print('Violations:')
        for vv in v:
            print('-', vv)
        sys.exit(1)
    print('No violations')
