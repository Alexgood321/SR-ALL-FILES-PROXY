#!/usr/bin/env python3
"""Validate the published Shadowrocket base config and routing module."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import ipaddress
from pathlib import Path
import re
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
    "REJECT-VIDEO",
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
CIDR_TOKEN_RE = re.compile(r"\b(IP-CIDR6|IP-CIDR),([^,()]+)(?:,no-resolve)?")
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


@dataclass(frozen=True)
class RuleEntry:
    position: int
    rule_type: str
    target: str
    policy: str
    raw: str


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


def validate_network(rule_type: str, target: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    try:
        network = ipaddress.ip_network(target, strict=True)
    except ValueError as error:
        raise ValueError(
            f"{rule_type} has invalid or non-canonical network {target!r}: {error}"
        ) from error
    if rule_type == "IP-CIDR" and network.version != 4:
        raise ValueError("IP-CIDR requires an IPv4 network")
    if rule_type == "IP-CIDR6" and network.version != 6:
        raise ValueError("IP-CIDR6 requires an IPv6 network")
    return network


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
        validate_network(rule_type, fields[1])
        policy = fields[2]
    elif rule_type in LOGICAL_TYPES:
        fields = split_top_level(line)
        if len(fields) != 3:
            raise ValueError(f"{rule_type} requires type, expression and policy")
        if not fields[1].startswith("((") or not fields[1].endswith("))"):
            raise ValueError(f"{rule_type} expression must be wrapped in double parentheses")
        for nested_type, nested_target in CIDR_TOKEN_RE.findall(fields[1]):
            validate_network(nested_type, nested_target)
        policy = fields[2]
    else:
        raise ValueError(f"unsupported rule type {rule_type}")

    if policy not in ALLOWED_POLICIES:
        raise ValueError(f"missing or unsupported policy {policy!r}")
    return policy


def parse_semantic_entry(position: int, rule: str, policy: str) -> RuleEntry | None:
    rule_type = rule.split(",", 1)[0]
    if rule_type not in SIMPLE_TYPES | IP_TYPES:
        return None
    fields = rule.split(",")
    return RuleEntry(
        position=position,
        rule_type=rule_type,
        target=fields[1].strip().lower(),
        policy=policy,
        raw=rule,
    )


def domain_is_within_suffix(domain: str, suffix: str) -> bool:
    domain = domain.lower().rstrip(".")
    suffix = suffix.lower().rstrip(".")
    return domain == suffix or domain.endswith("." + suffix)


def semantic_domain_checks(entries: list[RuleEntry]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    domain_entries = [
        entry
        for entry in entries
        if entry.rule_type in {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"}
    ]

    for index, earlier in enumerate(domain_entries):
        for later in domain_entries[index + 1 :]:
            shadowed = False

            if earlier.rule_type == "DOMAIN" and later.rule_type == "DOMAIN":
                shadowed = earlier.target == later.target
            elif earlier.rule_type == "DOMAIN-SUFFIX":
                if later.rule_type in {"DOMAIN", "DOMAIN-SUFFIX"}:
                    shadowed = domain_is_within_suffix(later.target, earlier.target)

            if shadowed:
                message = (
                    f"active rule {later.position} is shadowed by earlier rule "
                    f"{earlier.position}: {earlier.raw} -> {later.raw}"
                )
                if earlier.policy != later.policy:
                    errors.append(f"{ROUTING_PATH}: semantic domain conflict: {message}")
                elif earlier.raw != later.raw:
                    warnings.append(f"WARNING semantic domain redundancy: {message}")
                continue

            if earlier.rule_type == "DOMAIN-KEYWORD":
                if later.rule_type in {"DOMAIN", "DOMAIN-SUFFIX"}:
                    if earlier.target in later.target and earlier.policy != later.policy:
                        warnings.append(
                            "WARNING possible DOMAIN-KEYWORD overlap: "
                            f"active rule {earlier.position} ({earlier.raw}) may match "
                            f"later rule {later.position} ({later.raw})"
                        )
                elif (
                    later.rule_type == "DOMAIN-KEYWORD"
                    and earlier.target == later.target
                    and earlier.policy != later.policy
                ):
                    errors.append(
                        f"{ROUTING_PATH}: semantic keyword conflict: active rule "
                        f"{later.position} is shadowed by earlier rule {earlier.position}: "
                        f"{earlier.raw} -> {later.raw}"
                    )

    return errors, warnings


def semantic_cidr_checks(entries: list[RuleEntry]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    parsed: list[tuple[RuleEntry, ipaddress.IPv4Network | ipaddress.IPv6Network]] = []

    for entry in entries:
        if entry.rule_type not in IP_TYPES:
            continue
        parsed.append((entry, ipaddress.ip_network(entry.target, strict=True)))

    for index, (earlier, earlier_network) in enumerate(parsed):
        for later, later_network in parsed[index + 1 :]:
            if earlier_network.version != later_network.version:
                continue

            if later_network.subnet_of(earlier_network):
                message = (
                    f"active rule {later.position} ({later.raw}) is contained by earlier "
                    f"rule {earlier.position} ({earlier.raw})"
                )
                if earlier.policy != later.policy:
                    errors.append(f"{ROUTING_PATH}: semantic CIDR conflict: {message}")
                elif earlier.raw != later.raw:
                    warnings.append(f"WARNING semantic CIDR redundancy: {message}")
            elif earlier_network.overlaps(later_network) and earlier.policy != later.policy:
                warnings.append(
                    "WARNING partial CIDR overlap with different policies: "
                    f"rule {earlier.position} ({earlier.raw}) <-> "
                    f"rule {later.position} ({later.raw})"
                )

    return errors, warnings


def semantic_host_checks(host_lines: list[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    parsed: list[tuple[int, str, str]] = []
    seen: dict[str, tuple[int, str]] = {}

    for position, line in enumerate(host_lines, 1):
        if "=" not in line:
            errors.append(f"{ROUTING_PATH}: [Host] entry {position} is missing '=': {line}")
            continue
        host, value = (part.strip() for part in line.split("=", 1))
        host_key = host.lower().rstrip(".")
        if not host_key or not value:
            errors.append(f"{ROUTING_PATH}: [Host] entry {position} is incomplete: {line}")
            continue

        previous = seen.get(host_key)
        if previous is not None:
            previous_position, previous_value = previous
            if previous_value != value:
                errors.append(
                    f"{ROUTING_PATH}: [Host] conflict for {host}: entry "
                    f"{previous_position}={previous_value!r}, entry {position}={value!r}"
                )
            else:
                warnings.append(
                    f"WARNING exact [Host] duplicate: entry {previous_position} and "
                    f"{position}: {host} = {value}"
                )
        else:
            seen[host_key] = (position, value)

        parsed.append((position, host_key, value))

    wildcards = [
        (position, host[2:], value)
        for position, host, value in parsed
        if host.startswith("*.") and len(host) > 2
    ]
    exacts = [
        (position, host, value)
        for position, host, value in parsed
        if not host.startswith("*.")
    ]

    for exact_position, exact_host, exact_value in exacts:
        for wildcard_position, wildcard_suffix, wildcard_value in wildcards:
            if (
                exact_host != wildcard_suffix
                and domain_is_within_suffix(exact_host, wildcard_suffix)
                and exact_value != wildcard_value
            ):
                warnings.append(
                    "WARNING [Host] exact/wildcard overlap with different values: "
                    f"entry {exact_position} ({exact_host} = {exact_value}) <-> "
                    f"entry {wildcard_position} (*.{wildcard_suffix} = {wildcard_value})"
                )

    return errors, warnings


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
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
    if "[Host]" not in routing_text:
        errors.append(f"{ROUTING_PATH}: missing [Host] section")

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
    semantic_entries: list[RuleEntry] = []
    for position, rule in enumerate(routing_rules, 1):
        if rule.startswith("RULE-SET,"):
            errors.append(f"{ROUTING_PATH}: nested RULE-SET is not allowed: {rule}")
            continue
        try:
            policy = validate_rule(rule)
            policies[policy] += 1
            entry = parse_semantic_entry(position, rule, policy)
            if entry is not None:
                semantic_entries.append(entry)
        except ValueError as error:
            errors.append(f"{ROUTING_PATH}: active rule {position}: {error}: {rule}")

    duplicates = {
        rule: count for rule, count in Counter(routing_rules).items() if count > 1
    }
    for rule, count in sorted(duplicates.items()):
        warnings.append(f"WARNING exact duplicate x{count}: {rule}")

    domain_errors, domain_warnings = semantic_domain_checks(semantic_entries)
    cidr_errors, cidr_warnings = semantic_cidr_checks(semantic_entries)
    host_errors, host_warnings = semantic_host_checks(section_lines(routing_text, "Host"))

    errors.extend(domain_errors)
    errors.extend(cidr_errors)
    errors.extend(host_errors)
    warnings.extend(domain_warnings)
    warnings.extend(cidr_warnings)
    warnings.extend(host_warnings)

    for warning in warnings:
        print(warning)

    print(f"Routing active rules: {len(routing_rules)}")
    for policy, count in sorted(policies.items()):
        print(f"  {policy}: {count}")
    print(f"Exact duplicate rule values: {len(duplicates)}")
    print(
        "Semantic V1: "
        f"errors={len(domain_errors) + len(cidr_errors) + len(host_errors)}, "
        f"warnings={len(domain_warnings) + len(cidr_warnings) + len(host_warnings)}"
    )
    print(
        "Semantic V1 scope: DOMAIN/DOMAIN-SUFFIX, conservative DOMAIN-KEYWORD, "
        "top-level CIDR containment/overlap, basic [Host] conflicts, and strict "
        "canonical CIDR syntax including CIDRs nested inside logical rules. "
        "Cross-class DOMAIN-vs-IP precedence is intentionally not inferred."
    )

    if errors:
        print("VALIDATION FAILED", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
