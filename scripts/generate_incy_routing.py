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
        "INCY documents geoip categories in DirectIp.",
        "RU IP traffic can be evaluated for DIRECT after domain rules.",
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
                        "Shadowrocket skip-proxy hostname/wildcard semantics have no documented 1:1 INCY field; several tokens are also covered by Unified.",
                        "No broader INCY domain rule is invented.",
                    ))
                continue

            canonical = str(network)
            if add_unique(profile["DirectIp"], seen["DirectIp"], canonical):
                counts["PORTED"] += 1
                items.append(Item(
                    "config/remote.conf", f"{key}: {token}", "PORTED",
                    f"DirectIp: {canonical}",
                    "Closest documented INCY equivalent for a network that must remain outside the proxy path.",
                    "Network remains DIRECT in the INCY profile.",
                ))
            else:
                counts["SKIPPED AS DUPLICATE"] += 1
                items.append(Item(
                    "config/remote.conf", f"{key}: {token}",
                    "SKIPPED AS DUPLICATE", f"DirectIp: {canonical}",
                    "The same canonical network was already emitted from remote.conf.",
                    "No policy loss.",
                ))

    counts["PORTED"] += 1
    items.append(Item(
        "config/remote.conf", "FINAL,PROXY", "PORTED", "GlobalProxy: true",
        "INCY GlobalProxy=true defines unmatched traffic as PROXY.",
        "Default route remains PROXY.",
    ))

    def consume_rule(source: str, line: str, *, ads_source: bool = False) -> None:
        rule_type, value, action, extras = parse_rule(line)
        if action not in SUPPORTED_ACTIONS:
            counts["UNSUPPORTED"] += 1
            items.append(Item(
                source, line, "UNSUPPORTED", None,
                "Rule syntax/action has no implemented safe mapping in this generator.",
                "Rule is omitted rather than widened.",
            ))
            return

        if ads_source and action != "REJECT":
            counts["UNSUPPORTED"] += 1
            items.append(Item(
                source, line, "UNSUPPORTED", None,
                "Ads source is expected to contain REJECT policy only for INCY Block mapping.",
                "Rule is omitted.",
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
                    "DOMAIN uses full: and DOMAIN-SUFFIX uses domain: to preserve Xray-style exact/suffix scope. INCY documents specific domains/categories but not these prefixes explicitly on its routing page.",
                    "Static intent is preserved; INCY client E2E must confirm matcher-prefix handling before activation.",
                ))
            else:
                counts["SKIPPED AS DUPLICATE"] += 1
                items.append(Item(
                    source, line, "SKIPPED AS DUPLICATE", f"{destination}: {mapped}",
                    "Identical emitted matcher already exists in the same INCY bucket.",
                    "No policy loss within the generated representation.",
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
                    "CIDR maps directly to the documented INCY IP bucket. Shadowrocket no-resolve has no separate standard INCY routing field.",
                    "Routing target is preserved; DNS-trigger semantics may differ under IPIfNonMatch and require E2E.",
                ))
            else:
                counts["SKIPPED AS DUPLICATE"] += 1
                items.append(Item(
                    source, line, "SKIPPED AS DUPLICATE", f"{destination}: {canonical}",
                    "Identical CIDR already exists in the same INCY bucket.",
                    "No policy loss within the generated representation.",
                ))
            return

        if rule_type == "DOMAIN-KEYWORD":
            reason = "INCY routing docs do not document a Shadowrocket DOMAIN-KEYWORD equivalent; converting it to domain/suffix would alter scope."
        elif rule_type in {"USER-AGENT", "PROCESS-NAME"}:
            reason = f"Standard INCY routing profile does not document a {rule_type} selector."
        elif rule_type in {"AND", "OR", "NOT"}:
            reason = "Standard INCY routing profile does not document Shadowrocket logical/PROTOCOL selectors; flattening them would broaden policy."
        else:
            reason = f"No safe implemented mapping for {rule_type}."

        counts["UNSUPPORTED"] += 1
        items.append(Item(source, line, "UNSUPPORTED", None, reason, "Rule is omitted rather than approximated."))

    for line in section_lines(unified_text, "Rule"):
        consume_rule("modules/Unified-Routing-System-DNS.sgmodule", line)
    for line in section_lines(ads_text, "Rule"):
        consume_rule("modules/Ads-Privacy-Block.sgmodule", line, ads_source=True)

    for line in section_lines(unified_text, "Host"):
        counts["INTENTIONALLY NOT PORTED"] += 1
        items.append(Item(
            "modules/Unified-Routing-System-DNS.sgmodule [Host]", line,
            "INTENTIONALLY NOT PORTED", None,
            "INCY DnsHosts is static domain→IP and is not equivalent to Shadowrocket server:system. INCY Domestic DNS is global for direct resources, not selective per host.",
            "Selective System DNS parity is not claimed; DnsHosts remains empty.",
        ))

    fallback = general.get("fallback-dns-server", "")
    counts["INTENTIONALLY NOT PORTED"] += 1
    items.append(Item(
        "config/remote.conf", f"fallback-dns-server = {fallback}",
        "INTENTIONALLY NOT PORTED", None,
        "Standard INCY routing JSON documents one Remote DNS and one Domestic DNS, not a Remote-DNS fallback chain equivalent to Shadowrocket fallback-dns-server.",
        "Cloudflare is configured as Remote DNS; ControlD fallback parity is not claimed.",
    ))

    counts["INTENTIONALLY NOT PORTED"] += 1
    items.append(Item(
        "config/remote.conf + Unified [Host]", "selective server:system",
        "INTENTIONALLY NOT PORTED", None,
        "No documented per-domain System DNS selector exists in the standard INCY routing profile. No arbitrary Domestic DNS provider is introduced.",
        "DomesticDNS* fields are intentionally omitted; INCY defaults/runtime must be evaluated before production activation.",
    ))

    counts["ADAPTED"] += 1
    items.append(Item(
        "config/remote.conf", f"dns-server = {dns_server}",
        "ADAPTED / E2E REQUIRED",
        "RemoteDNSType=DoH; RemoteDNSDomain=Cloudflare URL",
        "INCY Remote DNS is documented for proxy resources. Shadowrocket #proxy syntax is removed because the proxy path is represented by INCY's Remote DNS role.",
        "Closest documented mapping; runtime DNS parity remains unverified.",
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
    no_resolve_gaps = [item for item in items if item.status == "PORTED WITH SEMANTIC GAP"]
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
        "# INCY conversion report",
        "",
        "Generated from the current canonical Shadowrocket production policy. Static conversion audit only; not INCY device/runtime proof.",
        "",
        "## Sources",
        "",
    ]
    for path, digest in source_hashes.items():
        lines.append(f"- `{path}` — SHA256 `{digest}`")
    lines += [
        f"- Official INCY docs baseline commit: `{OFFICIAL_INCY_DOCS_COMMIT}`",
        f"- Routing docs: {OFFICIAL_INCY_ROUTING_DOC}",
        f"- Autorouting docs: {OFFICIAL_INCY_AUTOROUTING_DOC}",
        "- YouTube module/script: **not used as sources**.",
        "",
        "## Generated profile",
        "",
        f"- Stage-2 public URL: `{PUBLIC_PROFILE_URL}`",
        "- `GlobalProxy = true`: unmatched traffic stays PROXY (`FINAL,PROXY`).",
        "- `DomainStrategy = IPIfNonMatch`: domain rules first, then IP/GeoIP evaluation on misses.",
        "- Remote DNS: Cloudflare DoH from `remote.conf`.",
        "- `DnsHosts = {}`: `server:system` is not faked as static hosts.",
        "- `DomesticDNS*` omitted: no arbitrary Google/Yandex/other resolver is invented. Omitted fields may use INCY defaults and require device validation.",
        "- `RemoteDNSIP`, `Geoipurl`, `Geositeurl` omitted: canonical policy does not provide values that can be copied without inventing behavior; INCY bundled geo data is used implicitly.",
        "- `FakeDNS = false`.",
        "",
        "### Output counts",
        "",
    ]
    for key, value in output_counts.items():
        lines.append(f"- `{key}`: {value}")
    lines += ["", "### Conversion status counts", ""]
    for key in sorted(counts):
        lines.append(f"- `{key}`: {counts[key]}")

    lines += [
        "",
        "## Semantic gaps / not claimed as parity",
        "",
        f"- Selective `[Host] server:system`: **{len(host_items)} entries not ported 1:1**. INCY `DnsHosts` is static domain→IP, not a System-DNS selector.",
        "- Shadowrocket DNS fallback (`System DNS → retry → ControlD #proxy`, or `Cloudflare #proxy → ControlD #proxy`) has no documented equivalent Remote-DNS fallback chain in standard INCY routing JSON.",
        "- Domestic DNS in INCY is global for direct resources; Shadowrocket System DNS is selective. DNS parity is **not** claimed.",
        "- `USER-AGENT`, `PROCESS-NAME`, `DOMAIN-KEYWORD`, logical `AND`/`PROTOCOL` are not widened into approximate domain rules.",
        "- `no-resolve` has no separate standard INCY field. CIDRs are ported, but DNS-trigger semantics under `IPIfNonMatch` require E2E.",
        "- Exact `DOMAIN` is adapted to `full:...`; `DOMAIN-SUFFIX` to `domain:...` to preserve Xray-style scope. INCY docs say specific domains/categories are accepted but do not explicitly document these prefixes on the routing-profile page, so client E2E is required.",
        "- `geoip:ru` uses INCY bundled geo data; GeoIP dataset parity with Shadowrocket is unverified.",
        "- Shadowrocket first-match/module priority is not automatically equivalent to INCY bucket priority.",
        "",
        "## Unsupported Shadowrocket rules",
        "",
        "Every unsupported active `[Rule]` is listed; none is broadened.",
        "",
        "| Source rule | INCY equivalent | Status | Reason | Possible effect |",
        "|---|---|---|---|---|",
    ]
    for item in unsupported:
        raw = item.raw.replace("|", "\\|")
        reason = item.reason.replace("|", "\\|")
        effect = item.effect.replace("|", "\\|")
        lines.append(f"| `{raw}` | `NONE` | **UNSUPPORTED** | {reason} | {effect} |")

    lines += [
        "",
        "## Ported CIDRs with `no-resolve` semantic gap",
        "",
        f"Count: **{len(no_resolve_gaps)}**. Routing destination is carried over; the Shadowrocket `no-resolve` modifier itself is not.",
        "",
    ]
    for item in no_resolve_gaps:
        lines.append(f"- `{item.raw}` → `{item.destination}`")

    lines += [
        "",
        "## Other intentionally-not-ported items",
        "",
    ]
    for item in non_host_intentional:
        lines.append(f"- `{item.raw}` — {item.reason}")
    lines += [
        f"- Unified `[Host] server:system`: {len(host_items)} entries are uniformly NOT PORTED because no documented per-domain System-DNS equivalent exists.",
        "",
        "## Duplicate suppression",
        "",
        f"Count: **{len(duplicate_items)}**.",
    ]
    for item in duplicate_items:
        lines.append(f"- `{item.raw}` → `{item.destination}`")

    lines += [
        "",
        "## Potential cross-bucket overlaps requiring INCY E2E priority check",
        "",
        "These are not declared errors: Shadowrocket resolves them by first-match/module order. INCY bucket precedence must be verified on-device before calling behavior equivalent.",
        "",
    ]
    for name, pairs in overlaps.items():
        lines.append(f"### {name}: {len(pairs)}")
        lines.append("")
        for left, right in pairs:
            lines.append(f"- `{left}` ↔ `{right}`")
        lines.append("")

    lines += [
        "## Validation scope",
        "",
        "Generator/tests can prove deterministic static conversion, source coverage and JSON validity. They do **not** prove INCY import, matcher interpretation, DNS behavior, bucket priority, autorouting delivery, subscription headers, or device E2E. Those belong to the later Sub-Store/INCY stage.",
        "",
        "## Rollback",
        "",
        "This stage does not alter canonical Shadowrocket policy or subscription delivery. Rollback is reverting/removing the INCY-only generator, generated `incy/` files, tests and INCY validation workflow. Existing Shadowrocket assets/URLs remain untouched.",
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
