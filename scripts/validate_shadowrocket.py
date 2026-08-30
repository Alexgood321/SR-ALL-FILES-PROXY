#!/usr/bin/env python3
"""Validate the published Shadowrocket base config and routing module."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys


REMOTE_PATH = Path("config/remote.conf")
ROUTING_PATH = Path("modules/Unified-Routing-System-DNS.sgmodule")

ALLOWED_POLICIES = {
    "DIRECT",
    "PROXY",
    "REJECT",
    "REJECT-ARRAY",
    "REJECT-TINYGIF",
    "REJECT-DICT",
    "REJECT-200",
}
SIMPLE_TYPES = {
    "DOMAIN",
    "DOMAIN-SUFFIX",
    "DOMAIN-KEYWORD",
    "PROCESS-NAME",
    "USER-AGENT",
}
IP_TYPES = {"IP-CIDR", "IP-CIDR6"}
LOGICAL_TYPES = {"AND", "OR", "NOT"}
FORBIDDEN_REMOTE_MARKERS = {
    "voip-pack.list",
    "proxy.list",
    "rules/upstreams",
    "rules/tunneling.list",
    "rules/VK-Direct-Stable-Privacy-DNS-Test",
    "rules/Manual-DIRECT.list",
    "rules/Apple-DIRECT-System-DNS-MAX.list",
    "rules/BiP-DIRECT.list",
    "rules/Telegram-PROXY-Full.list",
    "rules/JumpDesktop-PROXY.list",
    "rules/Meta-FULL-FB-PROXY-Remote-DNS.list",
    "rules/WhatsApp-Companion-WIDE.list",
    "rules/Manual-Proxy.list",
    "rules/TikTok-HARD-PROXY.list",
    "blackmatrix7/ios_rule_script",
    "Semporia/TikTok-Unlock",
}


def section_lines(text: str, section: str) -> list[str]:
    result: list[str] = []
    active = False
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped == f"[{section}]":
            active = True
            continue
        if active and stripped.startswith("[") and stripped.endswith("]"):
            break
        if active and stripped and not stripped.startswith(("#", "!")):
            result.append(stripped)
    return result


def split_top_level(line: str) -> list[str]:
    fields: list[str] = []
    current: list[str] = []
    depth = 0
    for character in line:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth < 0:
                raise ValueError("unbalanced closing parenthesis")
        if character == "," and depth == 0:
            fields.append("".join(current))
            current = []
        else:
            current.append(character)
    if depth != 0:
        raise ValueError("unbalanced parentheses")
    fields.append("".join(current))
    return fields


def validate_rule(line: str) -> str:
    rule_type = line.split(",", 1)[0]
    if rule_type in SIMPLE_TYPES:
        fields = line.split(",")
        if len(fields) != 3:
            raise ValueError(f"{rule_type} requires exactly 3 fields")
        policy = fields[2]
    elif rule_type in IP_TYPES:
        fields = line.split(",")
        if len(fields) not in {3, 4}:
            raise ValueError(f"{rule_type} requires 3 fields plus optional no-resolve")
        if len(fields) == 4 and fields[3] != "no-resolve":
            raise ValueError(f"{rule_type} fourth field must be no-resolve")
        policy = fields[2]
    elif rule_type in LOGICAL_TYPES:
        fields = split_top_level(line)
        if len(fields) != 3:
            raise ValueError(f"{rule_type} requires type, expression and policy")
        if not fields[1].startswith("((") or not fields[1].endswith("))"):
            raise ValueError(f"{rule_type} expression must be wrapped in double parentheses")
        policy = fields[2]
    else:
        raise ValueError(f"unsupported rule type {rule_type}")

    if policy not in ALLOWED_POLICIES:
        raise ValueError(f"missing or unsupported policy {policy!r}")
    return policy


def main() -> int:
    errors: list[str] = []
    for path in (REMOTE_PATH, ROUTING_PATH):
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"{path}: file is missing or empty")

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    remote_text = REMOTE_PATH.read_text(encoding="utf-8")
    routing_text = ROUTING_PATH.read_text(encoding="utf-8")

    if "[Rule]" not in routing_text:
        errors.append(f"{ROUTING_PATH}: missing [Rule] section")

    remote_rules = section_lines(remote_text, "Rule")
    expected_remote_rules = ["GEOIP,RU,DIRECT", "FINAL,PROXY"]
    if remote_rules != expected_remote_rules:
        errors.append(
            f"{REMOTE_PATH}: expected only {expected_remote_rules}, got {remote_rules}"
        )
    if any(line.startswith("RULE-SET,") for line in remote_rules):
        errors.append(f"{REMOTE_PATH}: active RULE-SET remains after migration")
    for marker in sorted(FORBIDDEN_REMOTE_MARKERS):
        if marker in remote_text:
            errors.append(f"{REMOTE_PATH}: forbidden migrated reference remains: {marker}")

    routing_rules = section_lines(routing_text, "Rule")
    policies: Counter[str] = Counter()
    for line_number, rule in enumerate(routing_rules, 1):
        if rule.startswith("RULE-SET,"):
            errors.append(f"{ROUTING_PATH}: nested RULE-SET is not allowed: {rule}")
            continue
        try:
            policies[validate_rule(rule)] += 1
        except ValueError as error:
            errors.append(f"{ROUTING_PATH}: active rule {line_number}: {error}: {rule}")

    duplicates = {
        rule: count for rule, count in Counter(routing_rules).items() if count > 1
    }
    for rule, count in sorted(duplicates.items()):
        print(f"WARNING exact duplicate x{count}: {rule}")

    print(f"Routing active rules: {len(routing_rules)}")
    for policy, count in sorted(policies.items()):
        print(f"  {policy}: {count}")
    print(f"Exact duplicate rule values: {len(duplicates)}")

    if errors:
        print("VALIDATION FAILED", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
