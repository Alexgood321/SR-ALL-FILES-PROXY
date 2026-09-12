#!/usr/bin/env python3
"""Generate INCY routing from canonical Shadowrocket production policy.

Canonical sources only:
- config/remote.conf
- modules/Unified-Routing-System-DNS.sgmodule
- modules/Ads-Privacy-Block.sgmodule

YouTube/MITM assets are intentionally outside this conversion.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOTE = ROOT / "config/remote.conf"
UNIFIED = ROOT / "modules/Unified-Routing-System-DNS.sgmodule"
ADS = ROOT / "modules/Ads-Privacy-Block.sgmodule"
CANONICAL_SOURCES = (REMOTE, UNIFIED, ADS)
DEFAULT_OUTPUT = ROOT / "incy/incy-routing.json"
DEFAULT_REPORT = ROOT / "incy/conversion-report.md"

PROFILE_NAME = "VPN-All"
PUBLIC_PROFILE_URL = (
    "https://raw.githubusercontent.com/Alexgood321/SR-ALL-FILES-PROXY/"
    "main/incy/incy-routing.json"
)
OFFICIAL_INCY_DOCS_COMMIT = "ad467b959cd7c6157fd041416c260ab849a29a4f"
OFFICIAL_INCY_ROUTING_DOC = "https://docs.incy.cc/routing/"
OFFICIAL_INCY_AUTOROUTING_DOC = "https://docs.incy.cc/autorouting/"

DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX"}
IP_TYPES = {"IP-CIDR", "IP-CIDR6"}
SUPPORTED_ACTIONS = {"DIRECT", "PROXY", "REJECT"}
ARRAY_KEYS = (
    "DirectSites",
    "DirectIp",
    "ProxySites",
    "ProxyIp",
    "BlockSites",
    "BlockIp",
)


@dataclass(frozen=True)
class Item:
    source: str
    raw: str
    status: str
    destination: str | None
    reason: str
    effect: str


def section_lines(text: str, section: str) -> list[str]:
    result: list[str] = []
    active = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == f"[{section}]":
            active = True
            continue
        if active and line.startswith("[") and line.endswith("]"):
            break
        if active and line and not line.startswith(("#", "!")):
            result.append(line)
    return result


def settings(text: str, section: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in section_lines(text, section):
        if "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        result[key] = value
    return result


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_unique(bucket: list[str], seen: set[str], value: str) -> bool:
    if value in seen:
        return False
    seen.add(value)
    bucket.append(value)
    return True


def map_domain(rule_type: str, value: str) -> str:
    """Preserve exact-vs-suffix scope with Xray-style matcher notation.

    INCY documents specific domains/categories but not these prefixes explicitly on
    the routing page, so this mapping remains ADAPTED/E2E-required.
    """
    value = value.strip().lower().rstrip(".")
    if rule_type == "DOMAIN":
        return f"full:{value}"
    if rule_type == "DOMAIN-SUFFIX":
        return f"domain:{value}"
    raise ValueError(rule_type)


def parse_rule(line: str) -> tuple[str, str | None, str | None, list[str]]:
    rule_type = line.split(",", 1)[0].strip()
    if rule_type in DOMAIN_TYPES | IP_TYPES | {
        "DOMAIN-KEYWORD",
        "PROCESS-NAME",
        "USER-AGENT",
    }:
        fields = [part.strip() for part in line.split(",")]
        if len(fields) < 3:
            return rule_type, None, None, fields
        return rule_type, fields[1], fields[2], fields[3:]

    if rule_type in {"AND", "OR", "NOT"}:
        head, separator, action = line.rpartition(",")
        if not separator:
            return rule_type, None, None, []
        return rule_type, head[len(rule_type) + 1 :], action.strip(), []

    if rule_type == "GEOIP":
        fields = [part.strip() for part in line.split(",")]
        if len(fields) == 3:
            return rule_type, fields[1], fields[2], []

    if rule_type == "FINAL":
        fields = [part.strip() for part in line.split(",")]
        if len(fields) == 2:
            return rule_type, None, fields[1], []

    return rule_type, None, None, []


def convert() -> tuple[dict, list[Item], dict[str, int]]:
    remote_text = REMOTE.read_text(encoding="utf-8")
    unified_text = UNIFIED.read_text(encoding="utf-8")
    ads_text = ADS.read_text(encoding="utf-8")

    general = settings(remote_text, "General")
    remote_rules = section_lines(remote_text, "Rule")
    if remote_rules != ["GEOIP,RU,DIRECT", "FINAL,PROXY"]:
        raise RuntimeError(f"remote.conf routing baseline changed: {remote_rules!r}")

    dns_server = general.get("dns-server", "")
    if not dns_server.startswith("https://") or not dns_server.endswith("#proxy"):
        raise RuntimeError(f"unexpected dns-server: {dns_server!r}")

    profile = {
        "Name": PROFILE_NAME,
        "GlobalProxy": "true",
        "RemoteDNSType": "DoH",
        "RemoteDNSDomain": dns_server.removesuffix("#proxy"),
        "DnsHosts": {},
        "DirectSites": [],
        "DirectIp": [],
        "ProxySites": [],
        "ProxyIp": [],
        "BlockSites": [],
        "BlockIp": [],
        "DomainStrategy": "IPIfNonMatch",
        "FakeDNS": "false",
    }

    seen = {key: set() for key in ARRAY_KEYS}
    items: list[Item] = []
    counts: Counter[str] = Counter()

    add_unique(profile["DirectIp"], seen["DirectIp"], "geoip:ru")
    counts["PORTED"] += 1
    items.append(Item(
        "config/remote.conf", "GEOIP,RU,DIRECT", "PORTED",
        "DirectIp: geoip:ru",
        "INCY поддерживает категории geoip в DirectIp.",
        "Российские IP могут быть отправлены DIRECT после проверки доменных правил.",
    ))

    for key in ("skip-proxy", "tun-excluded-routes"):
        for token in general.get(key, "").split(","):
            token = token.strip()
            if not token:
                continue
            try:
                network = ipaddress.ip_network(token, strict=False)
            except ValueError:
                if key == "skip-proxy":
                    counts["INTENTIONALLY NOT PORTED"] += 1
                    items.append(Item(
                        "config/remote.conf", f"{key}: {token}",
                        "INTENTIONALLY NOT PORTED", None,
                        "Для hostname/wildcard из Shadowrocket skip-proxy нет документированного 1:1 поля INCY; часть токенов дополнительно покрывается Unified.",
                        "Более широкое доменное правило для INCY не придумывается.",
                    ))
                continue

            canonical = str(network)
            if add_unique(profile["DirectIp"], seen["DirectIp"], canonical):
                if key == "tun-excluded-routes":
                    counts["PORTED WITH SEMANTIC GAP"] += 1
                    status = "PORTED WITH SEMANTIC GAP"
                    reason = (
                        "Shadowrocket tun-excluded-routes выводит сеть за пределы TUN. "
                        "DirectIp в INCY лишь маршрутизирует её DIRECT внутри клиента и не является 1:1 исключением из TUN."
                    )
                    effect = "Сеть остаётся DIRECT, но полная семантическая эквивалентность TUN exclusion не заявляется."
                else:
                    counts["PORTED"] += 1
                    status = "PORTED"
                    reason = "Документированный DirectIp является ближайшим эквивалентом для CIDR из skip-proxy."
                    effect = "Сеть остаётся DIRECT в профиле INCY."
                items.append(Item(
                    "config/remote.conf", f"{key}: {token}", status,
                    f"DirectIp: {canonical}", reason, effect,
                ))
            else:
                counts["SKIPPED AS DUPLICATE"] += 1
                items.append(Item(
                    "config/remote.conf", f"{key}: {token}",
                    "SKIPPED AS DUPLICATE", f"DirectIp: {canonical}",
                    "Та же каноническая сеть уже была добавлена из remote.conf.",
                    "Потери политики нет.",
                ))

    counts["PORTED"] += 1
    items.append(Item(
        "config/remote.conf", "FINAL,PROXY", "PORTED", "GlobalProxy: true",
        "INCY GlobalProxy=true задаёт PROXY для трафика, не совпавшего с другими правилами.",
        "Маршрут по умолчанию остаётся PROXY.",
    ))

    def consume_rule(source: str, line: str, *, ads_source: bool = False) -> None:
        rule_type, value, action, extras = parse_rule(line)
        if action not in SUPPORTED_ACTIONS:
            counts["UNSUPPORTED"] += 1
            items.append(Item(
                source, line, "UNSUPPORTED", None,
                "Для этого синтаксиса/действия нет реализованного безопасного отображения в генераторе.",
                "Правило пропускается, а не расширяется приблизительным аналогом.",
            ))
            return

        if ads_source and action != "REJECT":
            counts["UNSUPPORTED"] += 1
            items.append(Item(
                source, line, "UNSUPPORTED", None,
                "Источник Ads должен переносить в INCY Block только политику REJECT.",
                "Правило пропускается.",
            ))
            return

        if rule_type in DOMAIN_TYPES and value:
            destination = {
                "DIRECT": "DirectSites", "PROXY": "ProxySites", "REJECT": "BlockSites"
            }[action]
            mapped = map_domain(rule_type, value)
            if add_unique(profile[destination], seen[destination], mapped):
                counts["ADAPTED"] += 1
                items.append(Item(
                    source, line, "ADAPTED / E2E REQUIRED", f"{destination}: {mapped}",
                    "DOMAIN переводится в full:, а DOMAIN-SUFFIX — в domain:, чтобы сохранить точную/суффиксную область Xray. Документация INCY описывает конкретные домены/категории, но явно не фиксирует эти префиксы на странице routing-профиля.",
                    "Статическое намерение сохранено; обработку префиксов нужно подтвердить E2E в клиенте INCY до активации.",
                ))
            else:
                counts["SKIPPED AS DUPLICATE"] += 1
                items.append(Item(
                    source, line, "SKIPPED AS DUPLICATE", f"{destination}: {mapped}",
                    "Идентичный matcher уже присутствует в том же INCY bucket.",
                    "Потери политики в сгенерированном представлении нет.",
                ))
            return

        if rule_type in IP_TYPES and value:
            destination = {
                "DIRECT": "DirectIp", "PROXY": "ProxyIp", "REJECT": "BlockIp"
            }[action]
            try:
                network = ipaddress.ip_network(value, strict=True)
            except ValueError as exc:
                raise RuntimeError(f"non-canonical CIDR in {source}: {line}: {exc}") from exc
            canonical = str(network)
            if add_unique(profile[destination], seen[destination], canonical):
                if "no-resolve" in extras:
                    counts["PORTED WITH SEMANTIC GAP"] += 1
                    status = "PORTED WITH SEMANTIC GAP"
                else:
                    counts["PORTED"] += 1
                    status = "PORTED"
                items.append(Item(
                    source, line, status, f"{destination}: {canonical}",
                    "CIDR напрямую переносится в документированный IP bucket INCY. Для Shadowrocket no-resolve нет отдельного стандартного поля INCY routing.",
                    "Назначение маршрута сохранено; DNS-семантика при IPIfNonMatch может отличаться и требует E2E.",
                ))
            else:
                counts["SKIPPED AS DUPLICATE"] += 1
                items.append(Item(
                    source, line, "SKIPPED AS DUPLICATE", f"{destination}: {canonical}",
                    "Идентичный CIDR уже присутствует в том же INCY bucket.",
                    "Потери политики в сгенерированном представлении нет.",
                ))
            return

        if rule_type == "DOMAIN-KEYWORD":
            reason = "Документация INCY routing не описывает эквивалент Shadowrocket DOMAIN-KEYWORD; преобразование в domain/suffix изменило бы область действия."
        elif rule_type in {"USER-AGENT", "PROCESS-NAME"}:
            reason = f"Стандартный routing-профиль INCY не документирует селектор {rule_type}."
        elif rule_type in {"AND", "OR", "NOT"}:
            reason = "Стандартный routing-профиль INCY не документирует логические/PROTOCOL-селекторы Shadowrocket; упрощение расширило бы политику."
        else:
            reason = f"Безопасное отображение для {rule_type} не реализовано."

        counts["UNSUPPORTED"] += 1
        items.append(Item(source, line, "UNSUPPORTED", None, reason, "Правило пропускается, а не заменяется приблизительным аналогом."))

    for line in section_lines(unified_text, "Rule"):
        consume_rule("modules/Unified-Routing-System-DNS.sgmodule", line)
    for line in section_lines(ads_text, "Rule"):
        consume_rule("modules/Ads-Privacy-Block.sgmodule", line, ads_source=True)

    for line in section_lines(unified_text, "Host"):
        counts["INTENTIONALLY NOT PORTED"] += 1
        items.append(Item(
            "modules/Unified-Routing-System-DNS.sgmodule [Host]", line,
            "INTENTIONALLY NOT PORTED", None,
            "INCY DnsHosts — это статическое domain→IP и не эквивалент Shadowrocket server:system. Domestic DNS в INCY глобален для direct-ресурсов, а не выборочен по host.",
            "Паритет selective System DNS не заявляется; DnsHosts остаётся пустым.",
        ))

    fallback = general.get("fallback-dns-server", "")
    counts["INTENTIONALLY NOT PORTED"] += 1
    items.append(Item(
        "config/remote.conf", f"fallback-dns-server = {fallback}",
        "INTENTIONALLY NOT PORTED", None,
        "Стандартный INCY routing JSON документирует один Remote DNS и один Domestic DNS, но не цепочку Remote-DNS fallback, эквивалентную Shadowrocket fallback-dns-server.",
        "Cloudflare настроен как Remote DNS; паритет fallback на ControlD не заявляется.",
    ))

    counts["INTENTIONALLY NOT PORTED"] += 1
    items.append(Item(
        "config/remote.conf + Unified [Host]", "selective server:system",
        "INTENTIONALLY NOT PORTED", None,
        "В стандартном INCY routing-профиле нет документированного per-domain System DNS selector. Произвольный Domestic DNS провайдер не добавляется.",
        "Поля DomesticDNS* намеренно отсутствуют; defaults/runtime INCY нужно проверить до production activation.",
    ))

    counts["ADAPTED"] += 1
    items.append(Item(
        "config/remote.conf", f"dns-server = {dns_server}",
        "ADAPTED / E2E REQUIRED",
        "RemoteDNSType=DoH; RemoteDNSDomain=Cloudflare URL",
        "Remote DNS в INCY документирован для proxy-ресурсов. Суффикс Shadowrocket #proxy убирается, поскольку proxy-путь задаётся ролью Remote DNS в INCY.",
        "Это ближайшее документированное отображение; runtime DNS parity пока не подтверждён.",
    ))

    return profile, items, dict(counts)


def _matcher(value: str) -> tuple[str, str]:
    prefix, separator, body = value.partition(":")
    if separator and prefix in {"full", "domain"}:
        return prefix, body
    return "raw", value


def _domain_overlap(left: str, right: str) -> bool:
    left_type, left_value = _matcher(left)
    right_type, right_value = _matcher(right)
    if left_type == "raw" or right_type == "raw":
        return left == right
    if left_type == "full" and right_type == "full":
        return left_value == right_value
    if left_type == "domain" and right_type == "full":
        return right_value == left_value or right_value.endswith("." + left_value)
    if left_type == "full" and right_type == "domain":
        return left_value == right_value or left_value.endswith("." + right_value)
    return (
        left_value == right_value
        or left_value.endswith("." + right_value)
        or right_value.endswith("." + left_value)
    )


def _overlaps(profile: dict, left_key: str, right_key: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for left in profile[left_key]:
        for right in profile[right_key]:
            if _domain_overlap(left, right):
                result.append((left, right))
    return result


def render_report(profile: dict, items: list[Item], counts: dict[str, int]) -> str:
    source_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in CANONICAL_SOURCES}
    output_counts = {key: len(profile[key]) for key in ARRAY_KEYS}
    unsupported = [item for item in items if item.status == "UNSUPPORTED"]
    no_resolve_gaps = [
        item for item in items
        if item.status == "PORTED WITH SEMANTIC GAP" and "no-resolve" in item.raw
    ]
    tun_excluded_gaps = [
        item for item in items
        if item.status == "PORTED WITH SEMANTIC GAP" and item.raw.startswith("tun-excluded-routes:")
    ]
    non_host_intentional = [
        item for item in items
        if item.status == "INTENTIONALLY NOT PORTED" and "[Host]" not in item.source
    ]
    host_items = [item for item in items if item.source.endswith("[Host]")]
    duplicate_items = [item for item in items if item.status == "SKIPPED AS DUPLICATE"]
    overlaps = {
        "BlockSites ↔ DirectSites": _overlaps(profile, "BlockSites", "DirectSites"),
        "BlockSites ↔ ProxySites": _overlaps(profile, "BlockSites", "ProxySites"),
        "DirectSites ↔ ProxySites": _overlaps(profile, "DirectSites", "ProxySites"),
    }

    lines = [
        "# Отчёт конвертации INCY",
        "",
        "Сформирован из текущей канонической production-политики Shadowrocket. Это только аудит статической конвертации, а не подтверждение поведения INCY на устройстве/runtime.",
        "",
        "## Источники",
        "",
    ]
    for path, digest in source_hashes.items():
        lines.append(f"- `{path}` — SHA256 `{digest}`")
    lines += [
        f"- Базовый commit официальной документации INCY: `{OFFICIAL_INCY_DOCS_COMMIT}`",
        f"- Документация routing: {OFFICIAL_INCY_ROUTING_DOC}",
        f"- Документация autorouting: {OFFICIAL_INCY_AUTOROUTING_DOC}",
        "- YouTube module/script: **не используются как источники**.",
        "",
        "## Сгенерированный профиль",
        "",
        f"- Публичный URL stage 2: `{PUBLIC_PROFILE_URL}`",
        "- `GlobalProxy = true`: несовпавший трафик остаётся PROXY (`FINAL,PROXY`).",
        "- `DomainStrategy = IPIfNonMatch`: сначала доменные правила, затем IP/GeoIP при отсутствии совпадения.",
        "- Remote DNS: Cloudflare DoH из `remote.conf`.",
        "- `DnsHosts = {}`: `server:system` не подменяется статическими hosts.",
        "- `DomesticDNS*` отсутствуют: произвольный Google/Yandex/другой resolver не придумывается. Отсутствующие поля могут использовать defaults INCY и требуют проверки на устройстве.",
        "- `RemoteDNSIP`, `Geoipurl`, `Geositeurl` отсутствуют: canonical policy не содержит значений, которые можно перенести без изменения поведения; неявно используются встроенные geo-данные INCY.",
        "- `FakeDNS = false`.",
        "",
        "### Количество элементов в результате",
        "",
    ]
    for key, value in output_counts.items():
        lines.append(f"- `{key}`: {value}")
    lines += ["", "### Количество по статусам конвертации", ""]
    for key in sorted(counts):
        lines.append(f"- `{key}`: {counts[key]}")

    lines += [
        "",
        "## Семантические расхождения / паритет не заявляется",
        "",
        f"- Выборочный `[Host] server:system` (Selective `[Host] server:system`): **{len(host_items)} записей не перенесены 1:1**. INCY `DnsHosts` — статическое domain→IP, а не selector System DNS.",
        "- Резервная DNS-цепочка (DNS fallback) Shadowrocket (`System DNS → retry → ControlD #proxy` или `Cloudflare #proxy → ControlD #proxy`) не имеет документированного эквивалента Remote-DNS fallback в стандартном INCY routing JSON.",
        "- Domestic DNS в INCY глобален для direct-ресурсов; System DNS Shadowrocket выборочен. DNS parity **не заявляется**.",
        "- `USER-AGENT`, `PROCESS-NAME`, `DOMAIN-KEYWORD`, логические `AND`/`PROTOCOL` не расширяются приблизительными доменными правилами.",
        "- `no-resolve` не имеет отдельного стандартного поля INCY. CIDR переносится, но DNS-trigger semantics при `IPIfNonMatch` требует E2E.",
        "- Точное `DOMAIN` адаптируется в `full:...`, `DOMAIN-SUFFIX` — в `domain:...` (Exact `DOMAIN` is adapted), чтобы сохранить Xray-style область. Документация INCY допускает конкретные домены/категории, но явно не описывает эти префиксы на странице routing-профиля, поэтому нужен client E2E.",
        "- `tun-excluded-routes` не имеет 1:1 routing-эквивалента: Shadowrocket выводит сеть за пределы TUN, а INCY DirectIp только направляет её DIRECT внутри клиента.",
        "- `geoip:ru` использует встроенные geo-данные INCY; паритет GeoIP dataset с Shadowrocket не подтверждён.",
        "- First-match/module priority Shadowrocket не считается автоматически эквивалентным bucket priority INCY.",
        "",
        "## Неподдерживаемые правила Shadowrocket",
        "",
        "Ни одно активное неподдерживаемое `[Rule]` не расширяется; все такие правила перечислены ниже.",
        "",
        "| Исходное правило | Эквивалент INCY | Статус | Причина | Возможный эффект |",
        "|---|---|---|---|---|",
    ]
    for item in unsupported:
        raw = item.raw.replace("|", "\\|")
        reason = item.reason.replace("|", "\\|")
        effect = item.effect.replace("|", "\\|")
        lines.append(f"| `{raw}` | `NONE` | **UNSUPPORTED** | {reason} | {effect} |")

    lines += [
        "",
        "## Перенесённые CIDR с семантическим расхождением `no-resolve`",
        "",
        f"Количество: **{len(no_resolve_gaps)}**. Направление маршрута сохранено, сам модификатор Shadowrocket `no-resolve` — нет.",
        "",
    ]
    for item in no_resolve_gaps:
        lines.append(f"- `{item.raw}` → `{item.destination}`")

    lines += [
        "",
        "## `tun-excluded-routes`: семантическая адаптация",
        "",
        f"Количество уникальных CIDR, перенесённых как DirectIp с semantic gap: **{len(tun_excluded_gaps)}**.",
        "Shadowrocket исключает эти сети из TUN, тогда как стандартный INCY routing-профиль может только направить их DIRECT внутри клиента. Полный TUN parity не заявляется.",
        "",
    ]
    for item in tun_excluded_gaps:
        lines.append(f"- `{item.raw}` → `{item.destination}`")

    lines += [
        "",
        "## Остальные намеренно не перенесённые элементы",
        "",
    ]
    for item in non_host_intentional:
        lines.append(f"- `{item.raw}` — {item.reason}")
    lines += [
        f"- Unified `[Host] server:system`: {len(host_items)} записей единообразно имеют статус NOT PORTED, поскольку документированного per-domain System-DNS эквивалента нет.",
        "",
        "## Подавление дубликатов",
        "",
        f"Количество: **{len(duplicate_items)}**.",
    ]
    for item in duplicate_items:
        lines.append(f"- `{item.raw}` → `{item.destination}`")

    lines += [
        "",
        "## Возможные пересечения bucket, требующие проверки приоритета INCY E2E",
        "",
        "Это не объявляется ошибкой: Shadowrocket разрешает пересечения через first-match/module order. Приоритет bucket INCY нужно проверить на устройстве до утверждения эквивалентности поведения.",
        "",
    ]
    for name, pairs in overlaps.items():
        lines.append(f"### {name}: {len(pairs)}")
        lines.append("")
        for left, right in pairs:
            lines.append(f"- `{left}` ↔ `{right}`")
        lines.append("")

    lines += [
        "## Область подтверждения",
        "",
        "Генератор и тесты подтверждают детерминированную статическую конвертацию, покрытие источников и валидность JSON. Они **не подтверждают импорт INCY** (`do **not** prove INCY import`), трактовку matcher, DNS runtime, bucket priority, autorouting delivery, subscription headers или device E2E. Это относится к последующему этапу Sub-Store/INCY.",
        "",
        "## Откат (Rollback)",
        "",
        "Этот этап не меняет canonical Shadowrocket policy или delivery подписок. Откат — revert/remove INCY-only генератора, generated-файлов `incy/`, тестов и INCY validation workflow. Существующие Shadowrocket assets/URL остаются без изменений.",
        "",
    ]
    return "\n".join(lines)


def render_json(profile: dict) -> str:
    return json.dumps(profile, ensure_ascii=False, indent=2) + "\n"


def check_file(path: Path, expected: str) -> bool:
    return path.is_file() and path.read_text(encoding="utf-8") == expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    profile, items, counts = convert()
    json_text = render_json(profile)
    report_text = render_report(profile, items, counts)

    if args.check:
        ok_json = check_file(args.output, json_text)
        ok_report = check_file(args.report, report_text)
        if not ok_json:
            print(f"OUT OF DATE: {args.output}")
        if not ok_report:
            print(f"OUT OF DATE: {args.report}")
        return 0 if ok_json and ok_report else 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json_text, encoding="utf-8")
    args.report.write_text(report_text, encoding="utf-8")

    print("INCY routing generation PASS")
    for key in ARRAY_KEYS:
        print(f"{key}={len(profile[key])}")
    for key in sorted(counts):
        print(f"{key}={counts[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
