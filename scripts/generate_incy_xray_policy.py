#!/usr/bin/env python3
"""Generate credential-free native Xray routing/DNS policy for INCY Full Xray delivery.

Canonical policy inputs are imported from generate_incy_routing.py:
config/remote.conf, Unified Routing/System DNS, Ads/Privacy. YouTube/MITM is excluded.
The old incy-routing.json remains a separate compatibility artifact until Full Xray E2E.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import generate_incy_routing as legacy

ROOT = legacy.ROOT
REMOTE = legacy.REMOTE
UNIFIED = legacy.UNIFIED
ADS = legacy.ADS
CANONICAL_SOURCES = legacy.CANONICAL_SOURCES
OUTPUT = ROOT / "incy/xray-policy.json"
REPORT = ROOT / "incy/xray-conversion-report.md"
PUBLIC_URL = "https://raw.githubusercontent.com/Alexgood321/SR-ALL-FILES-PROXY/main/incy/xray-policy.json"
ACTION_TAG = {"DIRECT": "direct", "PROXY": "proxy", "REJECT": "block"}
SUPPORTED_ACTIONS = set(ACTION_TAG)
AND_RE = re.compile(r"^AND,\(\((?P<a>[^()]*)\),\((?P<b>[^()]*)\)\),(?P<action>DIRECT|PROXY|REJECT)$")


@dataclass(frozen=True)
class Record:
    source: str
    raw: str
    status: str
    reason: str


def canonical_network(value: str) -> str:
    return str(ipaddress.ip_network(value.strip(), strict=True))


def domain_matcher(kind: str, value: str) -> str:
    value = value.strip().lower().rstrip(".")
    if kind == "DOMAIN":
        return f"full:{value}"
    if kind == "DOMAIN-SUFFIX":
        return f"domain:{value}"
    if kind == "DOMAIN-KEYWORD":
        return f"keyword:{value}"
    raise ValueError(kind)


def source_inputs() -> tuple[str, str, dict[str, str]]:
    remote = REMOTE.read_text(encoding="utf-8")
    unified = UNIFIED.read_text(encoding="utf-8")
    ads = ADS.read_text(encoding="utf-8")
    general = legacy.settings(remote, "General")
    if legacy.section_lines(remote, "Rule") != ["GEOIP,RU,DIRECT", "FINAL,PROXY"]:
        raise RuntimeError("remote.conf routing baseline changed")
    if general.get("ipv6") != "false" or general.get("prefer-ipv6") != "false":
        raise RuntimeError("IPv4 baseline changed; review Xray queryStrategy mapping")
    return unified, ads, general


def strip_proxy_doh(value: str, name: str) -> str:
    if not value.startswith("https://") or not value.endswith("#proxy"):
        raise RuntimeError(f"unexpected {name}: {value!r}")
    return value.removesuffix("#proxy")


def host_matcher(host: str) -> str:
    host = host.strip().lower().rstrip(".")
    if host.startswith("*."):
        return f"domain:{host[2:]}"
    return f"full:{host}"


def selective_system_dns(unified: str) -> tuple[list[str], list[Record]]:
    result: list[str] = []
    seen: set[str] = set()
    records: list[Record] = []
    for line in legacy.section_lines(unified, "Host"):
        if "=" not in line:
            records.append(Record("Unified [Host]", line, "NOT PORTED", "Malformed Host entry."))
            continue
        left, right = (x.strip() for x in line.split("=", 1))
        if right != "server:system":
            records.append(Record("Unified [Host]", line, "NOT PORTED", f"Only server:system is mapped, got {right!r}."))
            continue
        matcher = host_matcher(left)
        if matcher in seen:
            records.append(Record("Unified [Host]", line, "SKIPPED AS DUPLICATE", "Duplicate DNS matcher."))
            continue
        seen.add(matcher)
        result.append(matcher)
        records.append(Record("Unified [Host]", line, "SEMANTIC ADAPTATION", "Mapped to native Xray priority DNS domains with localhost System DNS."))
    return result, records


def selector(kind: str, value: str, extras: list[str]) -> tuple[dict[str, Any], str]:
    if kind in {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD"}:
        return {"domain": [domain_matcher(kind, value)]}, "CONFIRMED STATIC MAPPING"
    if kind in legacy.IP_TYPES:
        status = "SEMANTIC ADAPTATION" if "no-resolve" in extras else "CONFIRMED STATIC MAPPING"
        return {"ip": [canonical_network(value)]}, status
    if kind == "PROCESS-NAME":
        return {"process": [value]}, "PLATFORM_DEPENDENT"
    raise ValueError(kind)


def parse_and(line: str) -> tuple[dict[str, Any] | None, str, str]:
    match = AND_RE.fullmatch(line)
    if not match:
        return None, "NOT PORTED", "Only two-clause AND with one PROTOCOL TCP/UDP clause is implemented."
    clauses = [[x.strip() for x in match.group(name).split(",")] for name in ("a", "b")]
    proto = next((c for c in clauses if c and c[0] == "PROTOCOL"), None)
    sel = next((c for c in clauses if c and c[0] != "PROTOCOL"), None)
    if proto is None or sel is None or len(proto) != 2:
        return None, "NOT PORTED", "AND must contain exactly one selector and one PROTOCOL clause."
    network = proto[1].lower()
    if network not in {"tcp", "udp"}:
        return None, "NOT PORTED", f"Unsupported PROTOCOL value {network!r}."
    if len(sel) < 2 or sel[0] not in legacy.DOMAIN_TYPES | legacy.IP_TYPES | {"DOMAIN-KEYWORD", "PROCESS-NAME"}:
        return None, "NOT PORTED", "Unsupported AND selector."
    body, status = selector(sel[0], sel[1], sel[2:])
    body.update({"type": "field", "network": network, "outboundTag": ACTION_TAG[match.group("action")]})
    if sel[0] == "PROCESS-NAME":
        status = "PLATFORM_DEPENDENT"
    return body, status, "Native Xray combines selector and network conditions in one field rule."


def rule_from_line(line: str, source: str, *, ads: bool = False) -> tuple[dict[str, Any] | None, Record]:
    kind, value, action, extras = legacy.parse_rule(line)
    if action not in SUPPORTED_ACTIONS:
        return None, Record(source, line, "NOT PORTED", "Unsupported action/syntax; omitted rather than approximated.")
    if ads and action != "REJECT":
        return None, Record(source, line, "NOT PORTED", "Ads source is allowed to map only REJECT to block.")
    if kind == "USER-AGENT":
        return None, Record(source, line, "NOT PORTED / REQUIRES E2E", "Xray attrs is not a safe 1:1 USER-AGENT substitute for general HTTPS/app traffic.")
    if kind == "AND":
        rule, status, reason = parse_and(line)
        return rule, Record(source, line, status, reason)
    if kind in {"OR", "NOT"}:
        return None, Record(source, line, "NOT PORTED", "No safe native converter implemented for this logical expression.")
    if value is None or kind not in legacy.DOMAIN_TYPES | legacy.IP_TYPES | {"DOMAIN-KEYWORD", "PROCESS-NAME"}:
        return None, Record(source, line, "NOT PORTED", f"No safe native mapping implemented for {kind}.")
    body, status = selector(kind, value, extras)
    body.update({"type": "field", "outboundTag": ACTION_TAG[action]})
    reason = "Native Xray matcher."
    if status == "PLATFORM_DEPENDENT":
        reason = "Xray process matching is native on Windows/Linux; INCY Android/iOS behavior requires platform E2E."
    elif status == "SEMANTIC ADAPTATION":
        reason = "CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch."
    return body, Record(source, line, status, reason)


def direct_networks(general: dict[str, str]) -> tuple[list[str], list[Record]]:
    networks: list[str] = []
    seen: set[str] = set()
    records: list[Record] = []
    for key in ("skip-proxy", "tun-excluded-routes"):
        for token in general.get(key, "").split(","):
            token = token.strip()
            if not token:
                continue
            try:
                net = str(ipaddress.ip_network(token, strict=False))
            except ValueError:
                records.append(Record("config/remote.conf", f"{key}: {token}", "NOT PORTED / COVERAGE CHECK", "Non-CIDR skip-proxy scope is not widened here; canonical domain policy comes from Unified."))
                continue
            if net in seen:
                records.append(Record("config/remote.conf", f"{key}: {token}", "SKIPPED AS DUPLICATE", "Duplicate local/private CIDR."))
                continue
            seen.add(net)
            networks.append(net)
            records.append(Record("config/remote.conf", f"{key}: {token}", "CONFIRMED STATIC MAPPING", "Mapped to native Xray direct IP rule."))
    return networks, records


def dns_config(general: dict[str, str], selective: list[str]) -> dict[str, Any]:
    cloudflare = strip_proxy_doh(general.get("dns-server", ""), "dns-server")
    controld = strip_proxy_doh(general.get("fallback-dns-server", ""), "fallback-dns-server")
    return {
        "queryStrategy": "UseIPv4",
        "disableFallback": False,
        "disableFallbackIfMatch": True,
        "enableParallelQuery": False,
        "tag": "dns-internal",
        "servers": [
            {"address": "localhost", "domains": selective, "skipFallback": True, "queryStrategy": "UseIPv4"},
            {"address": controld, "domains": selective, "skipFallback": True, "queryStrategy": "UseIPv4"},
            {"address": cloudflare, "queryStrategy": "UseIPv4"},
            {"address": controld, "queryStrategy": "UseIPv4"},
        ],
    }


def convert_xray() -> tuple[dict[str, Any], list[Record], dict[str, int]]:
    unified, ads_text, general = source_inputs()
    selective, records = selective_system_dns(unified)
    counts: Counter[str] = Counter(r.status for r in records)
    rules: list[dict[str, Any]] = []
    seen: set[str] = set()

    def append(rule: dict[str, Any] | None, record: Record) -> None:
        if rule is None:
            records.append(record)
            counts[record.status] += 1
            return
        key = json.dumps(rule, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if key in seen:
            duplicate = Record(record.source, record.raw, "SKIPPED AS DUPLICATE", "Identical native Xray rule already emitted; first occurrence retained.")
            records.append(duplicate)
            counts[duplicate.status] += 1
            return
        seen.add(key)
        rules.append(rule)
        records.append(record)
        counts[record.status] += 1

    for line in legacy.section_lines(ads_text, "Rule"):
        append(*rule_from_line(line, "modules/Ads-Privacy-Block.sgmodule", ads=True))

    append(
        {"type": "field", "inboundTag": ["dns-internal"], "outboundTag": "proxy"},
        Record("generated infrastructure", "dns.tag=dns-internal", "SEMANTIC ADAPTATION", "Forces Cloudflare/ControlD internal DNS traffic through proxy without routing localhost System DNS into a loop."),
    )

    for line in legacy.section_lines(unified, "Rule"):
        append(*rule_from_line(line, "modules/Unified-Routing-System-DNS.sgmodule"))

    networks, net_records = direct_networks(general)
    for record in net_records:
        if record.status != "CONFIRMED STATIC MAPPING":
            records.append(record)
            counts[record.status] += 1
    for net in networks:
        append(
            {"type": "field", "ip": [net], "outboundTag": "direct"},
            Record("config/remote.conf", f"local/private {net}", "CONFIRMED STATIC MAPPING", "Local/private CIDR remains direct."),
        )

    append(
        {"type": "field", "ip": ["geoip:ru"], "outboundTag": "direct"},
        Record("config/remote.conf", "GEOIP,RU,DIRECT", "CONFIRMED STATIC MAPPING", "Native Xray GeoIP matcher; geodata dataset parity still requires runtime verification."),
    )

    append(
        {"type": "field", "ip": ["0.0.0.0/0", "::/0"], "outboundTag": "proxy"},
        Record("config/remote.conf", "FINAL,PROXY", "SEMANTIC ADAPTATION", "Explicit universal IP fallback preserves IPIfNonMatch/geoip evaluation; unresolved no-match still falls to first proxy outbound in Full Xray config."),
    )

    policy = {
        "dns": dns_config(general, selective),
        "routing": {"domainStrategy": "IPIfNonMatch", "rules": rules},
    }
    validate_shape(policy)
    return policy, records, dict(counts)


def validate_shape(policy: dict[str, Any]) -> None:
    if set(policy) != {"dns", "routing"}:
        raise RuntimeError("xray-policy must contain only dns and routing")
    dns = policy["dns"]
    routing = policy["routing"]
    if not isinstance(dns.get("servers"), list) or len(dns["servers"]) != 4:
        raise RuntimeError("xray-policy DNS topology changed unexpectedly")
    if routing.get("domainStrategy") != "IPIfNonMatch" or not isinstance(routing.get("rules"), list):
        raise RuntimeError("xray-policy routing shape invalid")
    allowed = {"proxy", "direct", "block"}
    for idx, rule in enumerate(routing["rules"]):
        if rule.get("type") != "field" or rule.get("outboundTag") not in allowed:
            raise RuntimeError(f"invalid routing rule #{idx}: {rule!r}")
    serialized = json.dumps(policy, ensure_ascii=False).lower()
    for secret in ("uuid", "password", "privatekey", "publickey", "shortid"):
        if f'"{secret}"' in serialized:
            raise RuntimeError("credential-bearing field leaked into xray-policy")


def validation_config(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "inbounds": [],
        "outbounds": [
            {"tag": "proxy", "protocol": "freedom", "settings": {}},
            {"tag": "direct", "protocol": "freedom", "settings": {}},
            {"tag": "block", "protocol": "blackhole", "settings": {}},
        ],
        "dns": policy["dns"],
        "routing": policy["routing"],
    }


def render_report(policy: dict[str, Any], records: list[Record], counts: dict[str, int]) -> str:
    selective = policy["dns"]["servers"][0]["domains"]
    unsupported = [r for r in records if r.status.startswith("NOT PORTED")]
    platform = [r for r in records if r.status == "PLATFORM_DEPENDENT"]
    adaptations = [r for r in records if r.status == "SEMANTIC ADAPTATION"]
    lines = [
        "# INCY Full Xray conversion report", "",
        "Static repository conversion only. It does not prove Sub-Store delivery or INCY device E2E.", "",
        "## Source of truth", "",
    ]
    for path in CANONICAL_SOURCES:
        lines.append(f"- `{path.relative_to(ROOT)}` — SHA256 `{legacy.sha256(path)}`")
    lines += [
        "- YouTube/MITM files: **not used**.", "",
        "## Generated native policy", "",
        f"- `{PUBLIC_URL}`", f"- Routing rules: **{len(policy['routing']['rules'])}**", f"- Selective System DNS matchers: **{len(selective)}**",
        "- Intended use: Sub-Store embeds this `dns` + `routing` into every INCY Full Xray server config.",
        "- No `autorouting`, routing header or separate routing profile is produced by this artifact.",
        "- Legacy `incy/incy-routing.json` remains compatibility/diagnostic only until Full Xray E2E.", "",
        "## Native mapping", "",
        "- DOMAIN → `full:`; DOMAIN-SUFFIX → `domain:`; DOMAIN-KEYWORD → `keyword:`.",
        "- IP-CIDR/IP-CIDR6/GEOIP use native Xray `ip` matchers.",
        "- AND(selector + PROTOCOL TCP/UDP) stays one rule with both conditions.",
        "- PROCESS-NAME → native `process`, status **PLATFORM_DEPENDENT**.",
        "- USER-AGENT → **NOT PORTED / REQUIRES E2E**; `attrs` is not treated as 1:1.",
        "- Order: Ads BLOCK → DNS infrastructure guard → Unified source order → local/private DIRECT → GEOIP RU DIRECT → explicit FINAL PROXY.", "",
        "## DNS architecture", "",
        "Generated serial resolver topology:",
        "1. selective domains: `localhost` System DNS → ControlD DoH; Cloudflare is excluded from that matched list;",
        "2. ordinary domains: Cloudflare DoH → ControlD DoH;",
        "3. non-local DoH is tagged `dns-internal` and routed to proxy; localhost remains local.",
        "`queryStrategy=UseIPv4` is a DNS-level adaptation only, not a claim of full parity with Shadowrocket `ipv6=false` for every platform/outbound.",
        "Shadowrocket's observed extra retry of the same System DNS is **not claimed as reproduced**.",
        "DNS ARCHITECTURE: IMPLEMENTED STATICALLY. DNS PARITY: NOT TESTED.", "",
        "## Status counts", "",
    ]
    for key in sorted(counts):
        lines.append(f"- `{key}`: {counts[key]}")
    lines += ["", "## PLATFORM_DEPENDENT", ""]
    lines += [f"- `{r.raw}` — {r.reason}" for r in platform] or ["- None."]
    lines += ["", "## NOT PORTED / REQUIRES E2E", ""]
    lines += [f"- `{r.raw}` — **{r.status}** — {r.reason}" for r in unsupported] or ["- None."]
    lines += ["", "## SEMANTIC ADAPTATION", ""]
    lines += [f"- `{r.raw}` — {r.reason}" for r in adaptations] or ["- None."]
    lines += [
        "", "## Not proved by this stage", "",
        "- VLESS/Trojan/VMess server-link → proxy outbound conversion and credential preservation;",
        "- Sub-Store fetch/cache/LKG/fail-safe; INCY headers/client detection;",
        "- no separate Routing Profile in INCY UI; iOS/Android/Desktop routing/DNS runtime;",
        "- HAPP and Shadowrocket regression.",
        "These remain Alpha/Sub-Store E2E work and must not inherit PASS from repository CI.", "",
        "## Rollback", "",
        "Revert the native generator/tests/workflow/generated Xray artifacts. Canonical Shadowrocket files and existing client delivery remain untouched.", "",
    ]
    return "\n".join(lines)


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write-validation-config", type=Path)
    args = parser.parse_args()

    policy, records, counts = convert_xray()
    output_text = render(policy)
    report_text = render_report(policy, records, counts)
    if args.write_validation_config:
        args.write_validation_config.parent.mkdir(parents=True, exist_ok=True)
        args.write_validation_config.write_text(render(validation_config(policy)), encoding="utf-8")
    if args.check:
        ok_output = args.output.is_file() and args.output.read_text(encoding="utf-8") == output_text
        ok_report = args.report.is_file() and args.report.read_text(encoding="utf-8") == report_text
        if not ok_output:
            print(f"OUT OF DATE: {args.output}")
        if not ok_report:
            print(f"OUT OF DATE: {args.report}")
        return 0 if ok_output and ok_report else 1
    for path, text in ((args.output, output_text), (args.report, report_text)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print("INCY native Xray policy generation PASS")
    print(f"rules={len(policy['routing']['rules'])}")
    print(f"selective_system_dns={len(policy['dns']['servers'][0]['domains'])}")
    for key in sorted(counts):
        print(f"{key}={counts[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
