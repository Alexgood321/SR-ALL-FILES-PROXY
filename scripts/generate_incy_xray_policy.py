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
            records.append(Record("Unified [Host]", line, "NOT PORTED", "Некорректная запись Host."))
            continue
        left, right = (x.strip() for x in line.split("=", 1))
        if right != "server:system":
            records.append(Record("Unified [Host]", line, "NOT PORTED", f"Переносится только server:system, получено {right!r}."))
            continue
        matcher = host_matcher(left)
        if matcher in seen:
            records.append(Record("Unified [Host]", line, "SKIPPED AS DUPLICATE", "Дублирующий DNS matcher."))
            continue
        seen.add(matcher)
        result.append(matcher)
        records.append(Record("Unified [Host]", line, "SEMANTIC ADAPTATION", "Преобразовано в priority domains нативного Xray DNS с localhost System DNS."))
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
        return None, "NOT PORTED", "Реализован только AND из двух условий, одно из которых PROTOCOL TCP/UDP."
    clauses = [[x.strip() for x in match.group(name).split(",")] for name in ("a", "b")]
    proto = next((c for c in clauses if c and c[0] == "PROTOCOL"), None)
    sel = next((c for c in clauses if c and c[0] != "PROTOCOL"), None)
    if proto is None or sel is None or len(proto) != 2:
        return None, "NOT PORTED", "AND должен содержать ровно один selector и одно условие PROTOCOL."
    network = proto[1].lower()
    if network not in {"tcp", "udp"}:
        return None, "NOT PORTED", f"Неподдерживаемое значение PROTOCOL {network!r}."
    if len(sel) < 2 or sel[0] not in legacy.DOMAIN_TYPES | legacy.IP_TYPES | {"DOMAIN-KEYWORD", "PROCESS-NAME"}:
        return None, "NOT PORTED", "Неподдерживаемый selector внутри AND."
    body, status = selector(sel[0], sel[1], sel[2:])
    body.update({"type": "field", "network": network, "outboundTag": ACTION_TAG[match.group("action")]})
    if sel[0] == "PROCESS-NAME":
        status = "PLATFORM_DEPENDENT"
    return body, status, "Нативный Xray объединяет selector и network в одном field rule."


def rule_from_line(line: str, source: str, *, ads: bool = False) -> tuple[dict[str, Any] | None, Record]:
    kind, value, action, extras = legacy.parse_rule(line)
    if action not in SUPPORTED_ACTIONS:
        return None, Record(source, line, "NOT PORTED", "Неподдерживаемый action/синтаксис; правило пропущено вместо приблизительной замены.")
    if ads and action != "REJECT":
        return None, Record(source, line, "NOT PORTED", "Из Ads-источника разрешено переносить в block только REJECT.")
    if kind == "USER-AGENT":
        return None, Record(source, line, "NOT PORTED / REQUIRES E2E", "Xray attrs нельзя считать безопасным 1:1 эквивалентом USER-AGENT для общего HTTPS/app traffic.")
    if kind == "AND":
        rule, status, reason = parse_and(line)
        return rule, Record(source, line, status, reason)
    if kind in {"OR", "NOT"}:
        return None, Record(source, line, "NOT PORTED", "Для этого логического выражения не реализован безопасный нативный converter.")
    if value is None or kind not in legacy.DOMAIN_TYPES | legacy.IP_TYPES | {"DOMAIN-KEYWORD", "PROCESS-NAME"}:
        return None, Record(source, line, "NOT PORTED", f"Безопасное нативное отображение для {kind} не реализовано.")
    body, status = selector(kind, value, extras)
    body.update({"type": "field", "outboundTag": ACTION_TAG[action]})
    reason = "Нативный matcher Xray."
    if status == "PLATFORM_DEPENDENT":
        reason = "Process matching нативно поддерживается Xray на Windows/Linux; поведение INCY Android/iOS требует platform E2E."
    elif status == "SEMANTIC ADAPTATION":
        reason = "Целевой CIDR сохранён; у Shadowrocket no-resolve нет 1:1 модификатора Xray при IPIfNonMatch."
    return body, Record(source, line, status, reason)


def direct_networks(general: dict[str, str]) -> tuple[list[tuple[str, Record]], list[Record]]:
    emitted: list[tuple[str, Record]] = []
    ledger: list[Record] = []
    seen: set[str] = set()
    for key in ("skip-proxy", "tun-excluded-routes"):
        for token in general.get(key, "").split(","):
            token = token.strip()
            if not token:
                continue
            try:
                net = str(ipaddress.ip_network(token, strict=False))
            except ValueError:
                ledger.append(Record(
                    "config/remote.conf",
                    f"{key}: {token}",
                    "NOT PORTED / COVERAGE CHECK",
                    "Токен не является CIDR; область hostname/wildcard здесь не расширяется, каноническая доменная политика берётся из Unified.",
                ))
                continue
            if net in seen:
                ledger.append(Record(
                    "config/remote.conf",
                    f"{key}: {token}",
                    "SKIPPED AS DUPLICATE",
                    "Дублирующий local/private CIDR.",
                ))
                continue
            seen.add(net)
            if key == "tun-excluded-routes":
                record = Record(
                    "config/remote.conf",
                    f"{key}: {token}",
                    "SEMANTIC ADAPTATION",
                    "Shadowrocket исключает сеть из TUN; Xray direct/freedom только отправляет её напрямую внутри Xray и не является 1:1 TUN exclusion. Runtime parity не заявляется.",
                )
            else:
                record = Record(
                    "config/remote.conf",
                    f"{key}: {token}",
                    "CONFIRMED STATIC MAPPING",
                    "CIDR из skip-proxy преобразован в нативное Xray direct IP rule.",
                )
            emitted.append((net, record))
    return emitted, ledger


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
            duplicate = Record(record.source, record.raw, "SKIPPED AS DUPLICATE", "Идентичное нативное Xray rule уже было создано; сохранено первое вхождение.")
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
        Record("generated infrastructure", "dns.tag=dns-internal", "SEMANTIC ADAPTATION", "Внутренний DNS-трафик Cloudflare/ControlD принудительно идёт через proxy, при этом localhost System DNS не заводится в routing loop."),
    )

    for line in legacy.section_lines(unified, "Rule"):
        append(*rule_from_line(line, "modules/Unified-Routing-System-DNS.sgmodule"))

    network_rules, net_records = direct_networks(general)
    for record in net_records:
        records.append(record)
        counts[record.status] += 1
    for net, record in network_rules:
        append(
            {"type": "field", "ip": [net], "outboundTag": "direct"},
            record,
        )

    append(
        {"type": "field", "ip": ["geoip:ru"], "outboundTag": "direct"},
        Record("config/remote.conf", "GEOIP,RU,DIRECT", "CONFIRMED STATIC MAPPING", "Нативный GeoIP matcher Xray; паритет набора geodata всё ещё требует runtime verification."),
    )

    append(
        {"type": "field", "ip": ["0.0.0.0/0", "::/0"], "outboundTag": "proxy"},
        Record("config/remote.conf", "FINAL,PROXY", "SEMANTIC ADAPTATION", "Явный универсальный IP fallback сохраняет проверку IPIfNonMatch/geoip; unresolved no-match всё равно попадает в первый proxy outbound Full Xray config."),
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
        "# Отчёт конвертации INCY Full Xray", "",
        "Только статическая конвертация внутри репозитория. Она не подтверждает delivery Sub-Store или INCY device E2E.", "",
        "## Source of truth", "",
    ]
    for path in CANONICAL_SOURCES:
        lines.append(f"- `{path.relative_to(ROOT)}` — SHA256 `{legacy.sha256(path)}`")
    lines += [
        "- YouTube/MITM файлы: **не используются**.", "",
        "## Сгенерированная нативная policy", "",
        f"- `{PUBLIC_URL}`", f"- Routing rules: **{len(policy['routing']['rules'])}**", f"- Selective System DNS matchers: **{len(selective)}**",
        "- Назначение: Sub-Store встраивает эти `dns` + `routing` в каждый INCY Full Xray server config.",
        "- Артефакт не создаёт `autorouting`, routing header или отдельный routing profile (No `autorouting`).",
        "- Legacy `incy/incy-routing.json` остаётся compatibility/diagnostic до Full Xray E2E.", "",
        "## Нативное отображение", "",
        "- DOMAIN → `full:`; DOMAIN-SUFFIX → `domain:`; DOMAIN-KEYWORD → `keyword:`.",
        "- IP-CIDR/IP-CIDR6/GEOIP используют нативные Xray `ip` matchers.",
        "- AND(selector + PROTOCOL TCP/UDP) остаётся одним rule с обоими условиями.",
        "- PROCESS-NAME → нативный `process`, статус **PLATFORM_DEPENDENT**.",
        "- USER-AGENT → **NOT PORTED / REQUIRES E2E**; `attrs` не считается 1:1 заменой.",
        "- Порядок: Ads BLOCK → DNS infrastructure guard → исходный порядок Unified → local/private DIRECT → GEOIP RU DIRECT → явный FINAL PROXY.",
        "- `tun-excluded-routes` → DIRECT/freedom только как **SEMANTIC ADAPTATION**: Xray routing не воспроизводит исключение сети из TUN 1:1.", "",
        "## Архитектура DNS", "",
        "Сгенерированная последовательная topology resolver:",
        "1. selective domains: `localhost` System DNS → ControlD DoH; Cloudflare исключён из matched-list;",
        "2. обычные домены: Cloudflare DoH → ControlD DoH;",
        "3. non-local DoH получает tag `dns-internal` и маршрутизируется через proxy; localhost остаётся локальным.",
        "`queryStrategy=UseIPv4` — только DNS-level adaptation, а не заявление полного parity с Shadowrocket `ipv6=false` для каждой платформы/outbound.",
        "Наблюдавшийся в Shadowrocket дополнительный retry того же System DNS **не заявляется воспроизведённым**.",
        "DNS ARCHITECTURE: IMPLEMENTED STATICALLY. DNS PARITY: NOT TESTED.", "",
        "## Количество по статусам", "",
    ]
    for key in sorted(counts):
        lines.append(f"- `{key}`: {counts[key]}")
    lines += ["", "## PLATFORM_DEPENDENT", ""]
    lines += [f"- `{r.raw}` — {r.reason}" for r in platform] or ["- Нет."]
    lines += ["", "## NOT PORTED / REQUIRES E2E", ""]
    lines += [f"- `{r.raw}` — **{r.status}** — {r.reason}" for r in unsupported] or ["- Нет."]
    lines += ["", "## SEMANTIC ADAPTATION", ""]
    lines += [f"- `{r.raw}` — {r.reason}" for r in adaptations] or ["- Нет."]
    lines += [
        "", "## Что не подтверждено этим этапом", "",
        "- Преобразование VLESS/Trojan/VMess server-link → proxy outbound и сохранение credentials;",
        "- Sub-Store fetch/cache/LKG/fail-safe; INCY headers/client detection;",
        "- отсутствие отдельного Routing Profile в UI INCY; runtime routing/DNS на iOS/Android/Desktop;",
        "- regression HAPP и Shadowrocket (HAPP and Shadowrocket regression).",
        "Эти пункты остаются работой Alpha/Sub-Store E2E и не наследуют PASS от repository CI.", "",
        "## Откат", "",
        "Откатить native generator/tests/workflow/generated Xray artifacts. Canonical Shadowrocket-файлы и существующий client delivery остаются нетронутыми.", "",
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
