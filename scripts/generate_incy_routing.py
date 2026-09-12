#!/usr/bin/env python3
"""Generate the INCY routing profile from canonical Shadowrocket production policy.

Canonical sources are intentionally limited to:
- config/remote.conf
- modules/Unified-Routing-System-DNS.sgmodule
- modules/Ads-Privacy-Block.sgmodule

YouTube/MITM assets are intentionally outside this conversion.
"""

from __future__ import annotations

import argparse
import base64
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
    """Preserve Shadowrocket exact-vs-suffix scope with Xray-style matchers.

    INCY's official routing page documents specific domains/categories but does not
    spell out these matcher prefixes. Therefore this conversion is explicitly
    classified as ADAPTED/E2E-required in the generated report, not proven parity.
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

    # remote.conf: GEOIP,RU,DIRECT -> geoip:ru, FINAL,PROXY -> GlobalProxy=true.
    add_unique(profile["DirectIp"], seen["DirectIp"], "geoip:ru")
    counts["PORTED"] += 1
    items.append(
        Item(
            "config/remote.conf",
            "GEOIP,RU,DIRECT",
            "PORTED",
            "DirectIp: geoip:ru",
            "INCY documents geoip categories in DirectIp.",
            "RU IP traffic can be evaluated for DIRECT after domain rules.",
        )
    )

    # Carry network CIDRs from both skip-proxy and tun-excluded-routes. Hostname and
    # wildcard skip-proxy tokens are not guessed into INCY domain rules.
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
                    items.append(
                        Item(
                            "config/remote.conf",
                            f"{key}: {token}",
                            "INTENTIONALLY NOT PORTED",
                            None,
                            "Shadowrocket skip-proxy hostname/wildcard semantics do not have a documented 1:1 INCY field; several tokens are also covered by Unified.",
                            "No broader INCY domain rule is invented.",
                        )
                    )
                continue

            canonical = str(network)
            if add_unique(profile["DirectIp"], seen["DirectIp"], canonical):
                counts["PORTED"] += 1
                items.append(
                    Item(
                        "config/remote.conf",
                        f"{key}: {token}",
                        "PORTED",
                        f"DirectIp: {canonical}",
                        "Closest documented INCY equivalent for a network that must remain outside the proxy path.",
                        "Network remains DIRECT in the INCY profile.",
                    )
                )
            else:
                counts["SKIPPED AS DUPLICATE"] += 1
                items.append(
                    Item(
                        "config/remote.conf",
                        f"{key}: {token}",
                        "SKIPPED AS DUPLICATE",
                        f"DirectIp: {canonical}",
                        "The same canonical network was already emitted from remote.conf.",
                        "No policy loss.",
                    )
                )

    counts["PORTED"] += 1
    items.append(
        Item(
            "config/remote.conf",
            "FINAL,PROXY",
            "PORTED",
            "GlobalProxy: true",
            "INCY GlobalProxy=true defines unmatched traffic as PROXY.",
            "Default route remains PROXY.",
        )
    )

    def consume_rule(source: str, line: str, *, ads_source: bool = False) -> None:
        rule_type, value, action, extras = parse_rule(line)

        if action not in SUPPORTED_ACTIONS:
            counts["UNSUPPORTED"] += 1
            items.append(
                Item(
                    source,
                    line,
                    "UNSUPPORTED",
                    None,
                    "Rule syntax/action has no implemented safe mapping in this generator.",
                    "Rule is omitted rather than widened.",
                )
            )
            return

        if ads_source and action != "REJECT":
            counts["UNSUPPORTED"] += 1
            items.append(
                Item(
                    source,
                    line,
                    "UNSUPPORTED",
                    None,
                    "Ads source is expected to contain REJECT policy only for INCY Block mapping.",
                    "Rule is omitted.",
                )
            )
            return

        if rule_type in DOMAIN_TYPES and value:
            destination = {
                "DIRECT": "DirectSites",
                "PROXY": "ProxySites",
                "REJECT": "BlockSites",
            }[action]
            mapped = map_domain(rule_type, value)
            if add_unique(profile[destination], seen[destination], mapped):
                counts["ADAPTED"] += 1
                items.append(
                    Item(
                        source,
                        line,
                        "ADAPTED / E2E REQUIRED",
                        f"{destination}: {mapped}",
                        "DOMAIN is represented as full: and DOMAIN-SUFFIX as domain: to preserve Xray-style exact/suffix scope. INCY documents specific domains/categories but its routing page does not explicitly document these prefixes.",
                        "Intended scope is preserved statically; INCY client E2E must confirm matcher-prefix handling before production activation.",
                    )
                )
            else:
                counts["SKIPPED AS DUPLICATE"] += 1
                items.append(
                    Item(
                        source,
                        line,
                        "SKIPPED AS DUPLICATE",
                        f"{destination}: {mapped}",
                        "Identical emitted matcher already exists in the same INCY bucket.",
                        "No policy loss within the generated representation.",
                    )
                )
            return

        if rule_type in IP_TYPES and value:
            destination = {
                "DIRECT": "DirectIp",
                "PROXY": "ProxyIp",
                "REJECT": "BlockIp",
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
                items.append(
                    Item(
                        source,
                        line,
                        status,
                        f"{destination}: {canonical}",
                        "CIDR maps directly to the documented INCY IP bucket. Shadowrocket no-resolve has no separate field in the standard INCY routing profile.",
                        "Routing target is preserved; DNS-trigger semantics may differ under IPIfNonMatch and require E2E.",
                    )
                )
            else:
                counts["SKIPPED AS DUPLICATE"] += 1
                items.append(
                    Item(
                        source,
                        line,
                        "SKIPPED AS DUPLICATE",
                        f"{destination}: {canonical}",
                        "Identical CIDR already exists in the same INCY bucket.",
                        "No policy loss within the generated representation.",
                    )
                )
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
        items.append(
            Item(
                source,
                line,
                "UNSUPPORTED",
                None,
                reason,
                "Rule is omitted rather than approximated.",
            )
        )

    for line in section_lines(unified_text, "Rule"):
        consume_rule("modules/Unified-Routing-System-DNS.sgmodule", line)

    for line in section_lines(ads_text, "Rule"):
        consume_rule("modules/Ads-Privacy-Block.sgmodule", line, ads_source=True)

    # Never misuse DnsHosts for Shadowrocket server:system.
    for line in section_lines(unified_text, "Host"):
        counts["INTENTIONALLY NOT PORTED"] += 1
        items.append(
            Item(
                "modules/Unified-Routing-System-DNS.sgmodule [Host]",
                line,
                "INTENTIONALLY NOT PORTED",
                None,
                "INCY DnsHosts is static domain→IP and is not an equivalent of Shadowrocket server:system. INCY Domestic DNS is global for direct resources, not selective per host.",
                "Selective System DNS parity is not claimed; DnsHosts remains empty.",
            )
        )

    fallback = general.get("fallback-dns-server", "")
    counts["INTENTIONALLY NOT PORTED"] += 1
    items.append(
        Item(
            "config/remote.conf",
            f"fallback-dns-server = {fallback}",
            "INTENTIONALLY NOT PORTED",
            None,
            "Standard INCY routing JSON documents one Remote DNS and one Domestic DNS, not a Remote-DNS fallback chain equivalent to Shadowrocket fallback-dns-server.",
            "Cloudflare is configured as Remote DNS; ControlD fallback parity is not claimed.",
        )
    )

    counts["INTENTIONALLY NOT PORTED"] += 1
    items.append(
        Item(
            "config/remote.conf + Unified [Host]",
            "selective server:system",
            "INTENTIONALLY NOT PORTED",
            None,
            "No documented per-domain System DNS selector exists in the standard INCY routing profile. No arbitrary Domestic DNS provider is introduced.",
            "DomesticDNS* fields are intentionally omitted; INCY documented defaults/runtime must be evaluated before production activation.",
        )
    )

    counts["ADAPTED"] += 1
    items.append(
        Item(
            "config/remote.conf",
            f"dns-server = {dns_server}",
            "ADAPTED / E2E REQUIRED",
            "RemoteDNSType=DoH; RemoteDNSDomain=Cloudflare URL",
            "INCY Remote DNS is documented for proxy resources. Shadowrocket #proxy syntax is removed from the URL because the proxy path is represented by INCY's Remote DNS role.",
            "Closest documented mapping; runtime DNS parity remains unverified.",
        )
    )

    return profile, items, dict(counts)


def render_report(profile: dict, items: list[Item], counts: dict[str, int]) -> str:
    source_hashes = {
        str(path.relative_to(ROOT)): sha256(path) for path in CANONICAL_SOURCES
    }
    output_counts = {key: len(profile[key]) for key in ARRAY_KEYS}

    lines = [
        "# INCY conversion report",
        "",
        "Generated from the current canonical Shadowrocket production policy. This is a static conversion audit, not INCY device/runtime proof.",
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
        "- `modules/Youtube-Config.sgmodule` and `modules/youtube.response.js`: **not used as sources**.",
        "",
        "## Generated profile",
        "",
        f"- Public profile URL intended for stage-2 delivery: `{PUBLIC_PROFILE_URL}`",
        "- `GlobalProxy = true`: unmatched traffic is PROXY, matching `FINAL,PROXY` intent.",
        "- `DomainStrategy = IPIfNonMatch`: domain rules are checked first; domain misses can then be resolved/evaluated against IP/GeoIP rules such as `geoip:ru`.",
        "- Remote DNS: Cloudflare DoH from `remote.conf`; INCY documents Remote DNS as the DNS path for proxy resources.",
        "- `DnsHosts = {}`: Shadowrocket `server:system` is deliberately not converted into static hosts entries.",
        "- `DomesticDNS*` omitted: choosing Google/Yandex/another resolver without project evidence would invent policy. INCY documented defaults/runtime must be evaluated in stage 2.",
        "- `RemoteDNSIP` omitted: canonical `remote.conf` defines the DoH URL, not a bootstrap IP; the generator does not invent one.",
        "- `Geoipurl`/`Geositeurl` omitted: INCY documents bundled geo files; dataset parity with Shadowrocket is not assumed.",
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
        "## Important semantic gaps",
        "",
        "1. **Selective System DNS:** Shadowrocket `[Host] ... = server:system` has no documented 1:1 standard INCY routing-profile field. `DnsHosts` is static domain→IP and is not used as a substitute.",
        "2. **DNS fallback:** Shadowrocket runtime observed `server:system → retry System DNS → ControlD #proxy`; ordinary domains use `Cloudflare #proxy → ControlD #proxy`. Standard INCY routing JSON does not document an equivalent Remote-DNS fallback chain, so DNS parity is not claimed.",
        "3. **Domestic DNS:** INCY applies Domestic DNS to direct resources globally. Shadowrocket uses System DNS only for selected `[Host]` entries. No arbitrary Domestic resolver is introduced here; omitted fields may use INCY defaults and therefore require device validation.",
        "4. **Rule selectors:** `USER-AGENT`, `PROCESS-NAME`, logical `AND`/`PROTOCOL`, and `DOMAIN-KEYWORD` are not flattened into broader rules.",
        "5. **no-resolve:** IP/CIDR destinations are ported, but standard INCY routing JSON has no separate `no-resolve` modifier. `IPIfNonMatch` can therefore differ in when DNS is triggered.",
        "6. **First-match/priority:** Shadowrocket module priority places Ads REJECT above Unified. INCY precedence for overlapping block/direct/proxy entries must be confirmed in E2E before calling behavior equivalent.",
        "7. **Domain matcher representation:** exact `DOMAIN` becomes `full:...`; `DOMAIN-SUFFIX` becomes `domain:...` to preserve Xray-style scope. INCY docs state that specific domains/categories are accepted but do not explicitly document these prefixes on the routing-profile page; client E2E must confirm them before production activation.",
        "8. **Geo data:** `geoip:ru` uses INCY's bundled geo data because no third-party geo source is introduced. Geo dataset parity with Shadowrocket is unverified.",
        "",
        "## Rule-by-rule migration ledger",
        "",
        "| Source rule | INCY equivalent | Status | Reason | Possible effect |",
        "|---|---|---|---|---|",
    ]

    for item in items:
        source_rule = f"{item.source}: {item.raw}".replace("|", "\\|")
        destination = (item.destination or "NONE").replace("|", "\\|")
        reason = item.reason.replace("|", "\\|")
        effect = item.effect.replace("|", "\\|")
        lines.append(
            f"| `{source_rule}` | `{destination}` | **{item.status}** | {reason} | {effect} |"
        )

    lines += [
        "",
        "## Validation scope",
        "",
        "This generator/report can prove deterministic static conversion and JSON validity. It does **not** prove INCY import, domain-matcher interpretation, DNS behavior, routing priority, autorouting delivery, subscription headers, or device E2E. Those belong to the later Sub-Store/INCY delivery stage.",
        "",
        "## Rollback",
        "",
        "This stage does not alter the canonical Shadowrocket policy or subscription delivery. Rollback is simply reverting/removing the INCY-only generator, generated `incy/` files, tests and INCY validation workflow commit; existing Shadowrocket release assets and URLs remain untouched.",
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
    parser.add_argument(
        "--stdout-base64",
        action="store_true",
        help="Print generated artifacts as base64 markers (bootstrap/CI only).",
    )
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

    if args.stdout_base64:
        print("INCY_JSON_BASE64_BEGIN")
        print(base64.b64encode(json_text.encode("utf-8")).decode("ascii"))
        print("INCY_JSON_BASE64_END")
        print("INCY_REPORT_BASE64_BEGIN")
        print(base64.b64encode(report_text.encode("utf-8")).decode("ascii"))
        print("INCY_REPORT_BASE64_END")

    print("INCY routing generation PASS")
    for key in ARRAY_KEYS:
        print(f"{key}={len(profile[key])}")
    for key in sorted(counts):
        print(f"{key}={counts[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
