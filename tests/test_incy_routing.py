#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_incy_routing as gen  # noqa: E402


class IncyRoutingGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile, cls.items, cls.counts = gen.convert()
        cls.report = gen.render_report(cls.profile, cls.items, cls.counts)
        cls.unified_text = gen.UNIFIED.read_text(encoding="utf-8")
        cls.ads_text = gen.ADS.read_text(encoding="utf-8")

    def test_only_canonical_sources_are_used(self) -> None:
        self.assertEqual(
            tuple(path.relative_to(gen.ROOT).as_posix() for path in gen.CANONICAL_SOURCES),
            (
                "config/remote.conf",
                "modules/Unified-Routing-System-DNS.sgmodule",
                "modules/Ads-Privacy-Block.sgmodule",
            ),
        )
        source_names = "\n".join(path.as_posix() for path in gen.CANONICAL_SOURCES)
        self.assertNotIn("Youtube-Config", source_names)
        self.assertNotIn("youtube.response.js", source_names)

    def test_profile_uses_only_selected_documented_fields(self) -> None:
        expected_fields = {
            "Name",
            "GlobalProxy",
            "RemoteDNSType",
            "RemoteDNSDomain",
            "DnsHosts",
            "DirectSites",
            "DirectIp",
            "ProxySites",
            "ProxyIp",
            "BlockSites",
            "BlockIp",
            "DomainStrategy",
            "FakeDNS",
        }
        self.assertEqual(set(self.profile), expected_fields)
        for absent in (
            "DomesticDNSType",
            "DomesticDNSDomain",
            "DomesticDNSIP",
            "RemoteDNSIP",
            "Geoipurl",
            "Geositeurl",
            "useChunkFiles",
        ):
            self.assertNotIn(absent, self.profile)

    def test_core_routing_and_dns_mapping(self) -> None:
        self.assertEqual(self.profile["Name"], "VPN-All")
        self.assertEqual(self.profile["GlobalProxy"], "true")
        self.assertEqual(self.profile["RemoteDNSType"], "DoH")
        self.assertEqual(
            self.profile["RemoteDNSDomain"],
            "https://cloudflare-dns.com/dns-query",
        )
        self.assertEqual(self.profile["DnsHosts"], {})
        self.assertEqual(self.profile["DomainStrategy"], "IPIfNonMatch")
        self.assertEqual(self.profile["FakeDNS"], "false")
        self.assertIn("geoip:ru", self.profile["DirectIp"])
        self.assertIn("10.0.0.0/8", self.profile["DirectIp"])
        self.assertIn("172.16.0.0/12", self.profile["DirectIp"])
        self.assertIn("192.168.0.0/16", self.profile["DirectIp"])

    def test_all_output_arrays_are_unique(self) -> None:
        for key in gen.ARRAY_KEYS:
            values = self.profile[key]
            self.assertEqual(len(values), len(set(values)), key)

    def test_all_compatible_unified_rules_are_emitted(self) -> None:
        destinations = {
            "DIRECT": ("DirectSites", "DirectIp"),
            "PROXY": ("ProxySites", "ProxyIp"),
        }
        for line in gen.section_lines(self.unified_text, "Rule"):
            rule_type, value, action, _extras = gen.parse_rule(line)
            if action not in destinations or value is None:
                continue
            if rule_type in gen.DOMAIN_TYPES:
                key = destinations[action][0]
                self.assertIn(gen.map_domain(rule_type, value), self.profile[key], line)
            elif rule_type in gen.IP_TYPES:
                key = destinations[action][1]
                self.assertIn(value, self.profile[key], line)

    def test_all_compatible_ads_rules_are_emitted(self) -> None:
        for line in gen.section_lines(self.ads_text, "Rule"):
            rule_type, value, action, _extras = gen.parse_rule(line)
            self.assertEqual(action, "REJECT", line)
            self.assertIn(rule_type, gen.DOMAIN_TYPES | gen.IP_TYPES, line)
            if rule_type in gen.DOMAIN_TYPES:
                self.assertIn(gen.map_domain(rule_type, value), self.profile["BlockSites"], line)
            else:
                self.assertIn(value, self.profile["BlockIp"], line)

    def test_shadowrocket_specific_rules_are_not_broadened(self) -> None:
        unsupported_types = {"DOMAIN-KEYWORD", "USER-AGENT", "PROCESS-NAME", "AND", "OR", "NOT"}
        source_rules = []
        for line in gen.section_lines(self.unified_text, "Rule"):
            rule_type = line.split(",", 1)[0]
            if rule_type in unsupported_types:
                source_rules.append(line)
        self.assertTrue(source_rules)
        ledger = {item.raw: item for item in self.items if item.source == "modules/Unified-Routing-System-DNS.sgmodule"}
        for line in source_rules:
            self.assertIn(line, ledger)
            self.assertEqual(ledger[line].status, "UNSUPPORTED")
            self.assertIsNone(ledger[line].destination)

    def test_no_resolve_is_reported_as_semantic_gap(self) -> None:
        no_resolve = [
            line
            for line in gen.section_lines(self.unified_text, "Rule")
            if line.startswith(("IP-CIDR,", "IP-CIDR6,")) and line.endswith(",no-resolve")
        ]
        self.assertTrue(no_resolve)
        ledger = {item.raw: item for item in self.items if item.source == "modules/Unified-Routing-System-DNS.sgmodule"}
        for line in no_resolve:
            self.assertEqual(ledger[line].status, "PORTED WITH SEMANTIC GAP")

    def test_host_server_system_is_not_misused_as_dns_hosts(self) -> None:
        host_lines = gen.section_lines(self.unified_text, "Host")
        self.assertTrue(host_lines)
        host_items = [
            item
            for item in self.items
            if item.source == "modules/Unified-Routing-System-DNS.sgmodule [Host]"
        ]
        self.assertEqual(len(host_items), len(host_lines))
        self.assertTrue(all(item.status == "INTENTIONALLY NOT PORTED" for item in host_items))
        self.assertEqual(self.profile["DnsHosts"], {})

    def test_report_explicitly_records_dns_and_runtime_gaps(self) -> None:
        required = (
            "Selective `[Host] server:system`",
            "DNS fallback",
            "Domestic DNS",
            "no-resolve",
            "Exact `DOMAIN` is adapted",
            "do **not** prove INCY import",
            "Rollback",
        )
        for marker in required:
            self.assertIn(marker, self.report)

    def test_json_render_is_valid_and_deterministic(self) -> None:
        rendered = gen.render_json(self.profile)
        self.assertEqual(json.loads(rendered), self.profile)
        profile2, items2, counts2 = gen.convert()
        self.assertEqual(profile2, self.profile)
        self.assertEqual(items2, self.items)
        self.assertEqual(counts2, self.counts)
        self.assertEqual(gen.render_report(profile2, items2, counts2), self.report)


if __name__ == "__main__":
    unittest.main()
