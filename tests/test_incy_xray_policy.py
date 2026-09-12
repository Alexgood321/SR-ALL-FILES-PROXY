#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_incy_routing as legacy  # noqa: E402
import generate_incy_xray_policy as gen  # noqa: E402


class IncyXrayPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy, cls.records, cls.counts = gen.convert_xray()
        cls.rules = cls.policy["routing"]["rules"]
        cls.unified = gen.UNIFIED.read_text(encoding="utf-8")
        cls.ads = gen.ADS.read_text(encoding="utf-8")
        cls.report = gen.render_report(cls.policy, cls.records, cls.counts)

    def test_only_canonical_sources(self):
        self.assertEqual(gen.CANONICAL_SOURCES, legacy.CANONICAL_SOURCES)
        self.assertNotIn("Youtube", "\n".join(str(x) for x in gen.CANONICAL_SOURCES))

    def test_policy_contains_no_credentials(self):
        self.assertEqual(set(self.policy), {"dns", "routing"})
        text = json.dumps(self.policy).lower()
        for key in ("uuid", "password", "privatekey", "publickey", "shortid"):
            self.assertNotIn(f'"{key}"', text)

    def test_domain_exact_suffix_keyword(self):
        exact = gen.rule_from_line("DOMAIN,example.com,DIRECT", "fixture")[0]
        suffix = gen.rule_from_line("DOMAIN-SUFFIX,example.com,PROXY", "fixture")[0]
        keyword = gen.rule_from_line("DOMAIN-KEYWORD,example,PROXY", "fixture")[0]
        self.assertEqual(exact["domain"], ["full:example.com"])
        self.assertEqual(suffix["domain"], ["domain:example.com"])
        self.assertEqual(keyword["domain"], ["keyword:example"])

    def test_ipv4_ipv6(self):
        v4 = gen.rule_from_line("IP-CIDR,192.0.2.0/24,DIRECT", "fixture")[0]
        v6 = gen.rule_from_line("IP-CIDR6,2001:db8::/32,PROXY", "fixture")[0]
        self.assertEqual(v4["ip"], ["192.0.2.0/24"])
        self.assertEqual(v6["ip"], ["2001:db8::/32"])

    def test_no_resolve_is_semantic_adaptation(self):
        _rule, record = gen.rule_from_line("IP-CIDR,192.0.2.0/24,PROXY,no-resolve", "fixture")
        self.assertEqual(record.status, "SEMANTIC ADAPTATION")

    def test_direct_proxy_block(self):
        self.assertEqual(gen.rule_from_line("DOMAIN,a.example,DIRECT", "fixture")[0]["outboundTag"], "direct")
        self.assertEqual(gen.rule_from_line("DOMAIN,b.example,PROXY", "fixture")[0]["outboundTag"], "proxy")
        self.assertEqual(gen.rule_from_line("DOMAIN,c.example,REJECT", "fixture", ads=True)[0]["outboundTag"], "block")

    def test_and_udp_preserves_scope(self):
        line = "AND,((DOMAIN-SUFFIX,v.whatsapp.net),(PROTOCOL,UDP)),PROXY"
        rule, record = gen.rule_from_line(line, "fixture")
        self.assertEqual(rule["domain"], ["domain:v.whatsapp.net"])
        self.assertEqual(rule["network"], "udp")
        self.assertEqual(rule["outboundTag"], "proxy")
        self.assertNotEqual(record.status, "NOT PORTED")

    def test_and_ipv6_no_resolve(self):
        line = "AND,((IP-CIDR6,2a03:2880::/32,no-resolve),(PROTOCOL,UDP)),PROXY"
        rule, record = gen.rule_from_line(line, "fixture")
        self.assertEqual(rule["ip"], ["2a03:2880::/32"])
        self.assertEqual(rule["network"], "udp")
        self.assertEqual(record.status, "SEMANTIC ADAPTATION")

    def test_process_is_platform_dependent(self):
        rule, record = gen.rule_from_line("PROCESS-NAME,WhatsApp,PROXY", "fixture")
        self.assertEqual(rule["process"], ["WhatsApp"])
        self.assertEqual(record.status, "PLATFORM_DEPENDENT")

    def test_user_agent_not_ported(self):
        rule, record = gen.rule_from_line("USER-AGENT,WhatsApp*,PROXY", "fixture")
        self.assertIsNone(rule)
        self.assertEqual(record.status, "NOT PORTED / REQUIRES E2E")

    def test_selective_system_dns_extraction(self):
        selective = self.policy["dns"]["servers"][0]["domains"]
        self.assertTrue(selective)
        self.assertEqual(selective, self.policy["dns"]["servers"][1]["domains"])
        for line in legacy.section_lines(self.unified, "Host"):
            left, right = (x.strip() for x in line.split("=", 1))
            if right == "server:system":
                self.assertIn(gen.host_matcher(left), selective)

    def test_dns_order_and_proxy_guard(self):
        servers = self.policy["dns"]["servers"]
        self.assertEqual(servers[0]["address"], "localhost")
        self.assertIn("freedns.controld.com", servers[1]["address"])
        self.assertIn("cloudflare-dns.com", servers[2]["address"])
        self.assertIn("freedns.controld.com", servers[3]["address"])
        self.assertTrue(self.policy["dns"]["disableFallbackIfMatch"])
        self.assertFalse(self.policy["dns"]["enableParallelQuery"])
        guard = next(r for r in self.rules if r.get("inboundTag") == ["dns-internal"])
        self.assertEqual(guard["outboundTag"], "proxy")

    def test_geoip_ru_and_final_proxy_order(self):
        geo = {"type": "field", "ip": ["geoip:ru"], "outboundTag": "direct"}
        final = {"type": "field", "ip": ["0.0.0.0/0", "::/0"], "outboundTag": "proxy"}
        self.assertIn(geo, self.rules)
        self.assertIn(final, self.rules)
        self.assertLess(self.rules.index(geo), self.rules.index(final))
        self.assertEqual(self.rules[-1], final)

    def test_ads_rules_precede_unified(self):
        ads_first = legacy.section_lines(self.ads, "Rule")[0]
        unified_first = legacy.section_lines(self.unified, "Rule")[0]
        ads_rule = gen.rule_from_line(ads_first, "fixture", ads=True)[0]
        unified_rule = gen.rule_from_line(unified_first, "fixture")[0]
        self.assertLess(self.rules.index(ads_rule), self.rules.index(unified_rule))

    def test_unified_supported_rule_order_preserved(self):
        expected = []
        for line in legacy.section_lines(self.unified, "Rule"):
            rule, _record = gen.rule_from_line(line, "fixture")
            if rule is not None and rule not in expected:
                expected.append(rule)
        positions = [self.rules.index(rule) for rule in expected]
        self.assertEqual(positions, sorted(positions))

    def test_native_duplicates_removed(self):
        encoded = [json.dumps(r, sort_keys=True) for r in self.rules]
        self.assertEqual(len(encoded), len(set(encoded)))

    def test_validation_wrapper_has_full_xray_shape(self):
        config = gen.validation_config(self.policy)
        self.assertIn("inbounds", config)
        self.assertIn("outbounds", config)
        self.assertEqual(config["inbounds"], [])
        self.assertEqual([o["tag"] for o in config["outbounds"]], ["proxy", "direct", "block"])
        self.assertEqual(config["dns"], self.policy["dns"])
        self.assertEqual(config["routing"], self.policy["routing"])

    def test_report_marks_delivery_and_runtime_unverified(self):
        for marker in (
            "No `autorouting`",
            "DNS PARITY: NOT TESTED",
            "PLATFORM_DEPENDENT",
            "NOT PORTED / REQUIRES E2E",
            "HAPP and Shadowrocket regression",
        ):
            self.assertIn(marker, self.report)

    def test_deterministic(self):
        p2, r2, c2 = gen.convert_xray()
        self.assertEqual(p2, self.policy)
        self.assertEqual(r2, self.records)
        self.assertEqual(c2, self.counts)
        self.assertEqual(gen.render(self.policy), gen.render(p2))


if __name__ == "__main__":
    unittest.main()
