# INCY conversion report

Generated from the current canonical Shadowrocket production policy. Static conversion audit only; not INCY device/runtime proof.

## Sources

- `config/remote.conf` — SHA256 `78b60dd2c6a1c63ba863d07f56ee0035f747f5309a188d941e1ecf72059098d4`
- `modules/Unified-Routing-System-DNS.sgmodule` — SHA256 `dd6d66b2c222a1b8a53a3b8be26c6aac8908aa8b2228bfc8df9eaa04cea1d695`
- `modules/Ads-Privacy-Block.sgmodule` — SHA256 `2512e9115f9ec81fc52b8507e155c3aa8ddb501c74f511bd7a2676ad0fca8727`
- Official INCY docs baseline commit: `ad467b959cd7c6157fd041416c260ab849a29a4f`
- Routing docs: https://docs.incy.cc/routing/
- Autorouting docs: https://docs.incy.cc/autorouting/
- YouTube module/script: **not used as sources**.

## Generated profile

- Stage-2 public URL: `https://raw.githubusercontent.com/Alexgood321/SR-ALL-FILES-PROXY/main/incy/incy-routing.json`
- `GlobalProxy = true`: unmatched traffic stays PROXY (`FINAL,PROXY`).
- `DomainStrategy = IPIfNonMatch`: domain rules first, then IP/GeoIP evaluation on misses.
- Remote DNS: Cloudflare DoH from `remote.conf`.
- `DnsHosts = {}`: `server:system` is not faked as static hosts.
- `DomesticDNS*` omitted: no arbitrary Google/Yandex/other resolver is invented. Omitted fields may use INCY defaults and require device validation.
- `RemoteDNSIP`, `Geoipurl`, `Geositeurl` omitted: canonical policy does not provide values that can be copied without inventing behavior; INCY bundled geo data is used implicitly.
- `FakeDNS = false`.

### Output counts

- `DirectSites`: 221
- `DirectIp`: 25
- `ProxySites`: 125
- `ProxyIp`: 29
- `BlockSites`: 59
- `BlockIp`: 0

### Conversion status counts

- `ADAPTED`: 406
- `INTENTIONALLY NOT PORTED`: 300
- `PORTED`: 16
- `PORTED WITH SEMANTIC GAP`: 39
- `SKIPPED AS DUPLICATE`: 3
- `UNSUPPORTED`: 12

## Semantic gaps / not claimed as parity

- Selective `[Host] server:system`: **293 entries not ported 1:1**. INCY `DnsHosts` is static domain→IP, not a System-DNS selector.
- Shadowrocket DNS fallback (`System DNS → retry → ControlD #proxy`, or `Cloudflare #proxy → ControlD #proxy`) has no documented equivalent Remote-DNS fallback chain in standard INCY routing JSON.
- Domestic DNS in INCY is global for direct resources; Shadowrocket System DNS is selective. DNS parity is **not** claimed.
- `USER-AGENT`, `PROCESS-NAME`, `DOMAIN-KEYWORD`, logical `AND`/`PROTOCOL` are not widened into approximate domain rules.
- `no-resolve` has no separate standard INCY field. CIDRs are ported, but DNS-trigger semantics under `IPIfNonMatch` require E2E.
- Exact `DOMAIN` is adapted to `full:...`; `DOMAIN-SUFFIX` to `domain:...` to preserve Xray-style scope. INCY docs say specific domains/categories are accepted but do not explicitly document these prefixes on the routing-profile page, so client E2E is required.
- `geoip:ru` uses INCY bundled geo data; GeoIP dataset parity with Shadowrocket is unverified.
- Shadowrocket first-match/module priority is not automatically equivalent to INCY bucket priority.

## Unsupported Shadowrocket rules

Every unsupported active `[Rule]` is listed; none is broadened.

| Source rule | INCY equivalent | Status | Reason | Possible effect |
|---|---|---|---|---|
| `USER-AGENT,TikTok*,PROXY` | `NONE` | **UNSUPPORTED** | Standard INCY routing profile does not document a USER-AGENT selector. | Rule is omitted rather than approximated. |
| `DOMAIN-KEYWORD,tiktok,PROXY` | `NONE` | **UNSUPPORTED** | INCY routing docs do not document a Shadowrocket DOMAIN-KEYWORD equivalent; converting it to domain/suffix would alter scope. | Rule is omitted rather than approximated. |
| `DOMAIN-KEYWORD,-tiktokcdn-com,PROXY` | `NONE` | **UNSUPPORTED** | INCY routing docs do not document a Shadowrocket DOMAIN-KEYWORD equivalent; converting it to domain/suffix would alter scope. | Rule is omitted rather than approximated. |
| `DOMAIN-KEYWORD,musical.ly,PROXY` | `NONE` | **UNSUPPORTED** | INCY routing docs do not document a Shadowrocket DOMAIN-KEYWORD equivalent; converting it to domain/suffix would alter scope. | Rule is omitted rather than approximated. |
| `PROCESS-NAME,WhatsApp,PROXY` | `NONE` | **UNSUPPORTED** | Standard INCY routing profile does not document a PROCESS-NAME selector. | Rule is omitted rather than approximated. |
| `USER-AGENT,WhatsApp*,PROXY` | `NONE` | **UNSUPPORTED** | Standard INCY routing profile does not document a USER-AGENT selector. | Rule is omitted rather than approximated. |
| `AND,((DOMAIN-SUFFIX,v.whatsapp.net),(PROTOCOL,UDP)),PROXY` | `NONE` | **UNSUPPORTED** | Standard INCY routing profile does not document Shadowrocket logical/PROTOCOL selectors; flattening them would broaden policy. | Rule is omitted rather than approximated. |
| `AND,((DOMAIN-SUFFIX,mmg.whatsapp.net),(PROTOCOL,UDP)),PROXY` | `NONE` | **UNSUPPORTED** | Standard INCY routing profile does not document Shadowrocket logical/PROTOCOL selectors; flattening them would broaden policy. | Rule is omitted rather than approximated. |
| `AND,((DOMAIN-SUFFIX,media.whatsapp.net),(PROTOCOL,UDP)),PROXY` | `NONE` | **UNSUPPORTED** | Standard INCY routing profile does not document Shadowrocket logical/PROTOCOL selectors; flattening them would broaden policy. | Rule is omitted rather than approximated. |
| `AND,((IP-CIDR6,2a03:2880::/32,no-resolve),(PROTOCOL,UDP)),PROXY` | `NONE` | **UNSUPPORTED** | Standard INCY routing profile does not document Shadowrocket logical/PROTOCOL selectors; flattening them would broaden policy. | Rule is omitted rather than approximated. |
| `DOMAIN-KEYWORD,jumpdesktop,PROXY` | `NONE` | **UNSUPPORTED** | INCY routing docs do not document a Shadowrocket DOMAIN-KEYWORD equivalent; converting it to domain/suffix would alter scope. | Rule is omitted rather than approximated. |
| `DOMAIN-KEYWORD,radiorecord,DIRECT` | `NONE` | **UNSUPPORTED** | INCY routing docs do not document a Shadowrocket DOMAIN-KEYWORD equivalent; converting it to domain/suffix would alter scope. | Rule is omitted rather than approximated. |

## Ported CIDRs with `no-resolve` semantic gap

Count: **39**. Routing destination is carried over; the Shadowrocket `no-resolve` modifier itself is not.

- `IP-CIDR,62.60.230.167/32,PROXY,no-resolve` → `ProxyIp: 62.60.230.167/32`
- `IP-CIDR,31.77.158.107/32,PROXY,no-resolve` → `ProxyIp: 31.77.158.107/32`
- `IP-CIDR,91.108.4.0/22,PROXY,no-resolve` → `ProxyIp: 91.108.4.0/22`
- `IP-CIDR,91.108.8.0/22,PROXY,no-resolve` → `ProxyIp: 91.108.8.0/22`
- `IP-CIDR,91.108.12.0/22,PROXY,no-resolve` → `ProxyIp: 91.108.12.0/22`
- `IP-CIDR,91.108.16.0/22,PROXY,no-resolve` → `ProxyIp: 91.108.16.0/22`
- `IP-CIDR,91.108.20.0/22,PROXY,no-resolve` → `ProxyIp: 91.108.20.0/22`
- `IP-CIDR,91.108.56.0/22,PROXY,no-resolve` → `ProxyIp: 91.108.56.0/22`
- `IP-CIDR,91.105.192.0/23,PROXY,no-resolve` → `ProxyIp: 91.105.192.0/23`
- `IP-CIDR,95.161.64.0/20,PROXY,no-resolve` → `ProxyIp: 95.161.64.0/20`
- `IP-CIDR,149.154.160.0/20,PROXY,no-resolve` → `ProxyIp: 149.154.160.0/20`
- `IP-CIDR,185.76.151.0/24,PROXY,no-resolve` → `ProxyIp: 185.76.151.0/24`
- `IP-CIDR6,2001:67c:4e8::/48,PROXY,no-resolve` → `ProxyIp: 2001:67c:4e8::/48`
- `IP-CIDR6,2001:b28:f23d::/48,PROXY,no-resolve` → `ProxyIp: 2001:b28:f23d::/48`
- `IP-CIDR6,2001:b28:f23f::/48,PROXY,no-resolve` → `ProxyIp: 2001:b28:f23f::/48`
- `IP-CIDR6,2001:b28:f23c::/48,PROXY,no-resolve` → `ProxyIp: 2001:b28:f23c::/48`
- `IP-CIDR6,2a0a:f280::/32,PROXY,no-resolve` → `ProxyIp: 2a0a:f280::/32`
- `IP-CIDR,31.13.64.0/18,PROXY,no-resolve` → `ProxyIp: 31.13.64.0/18`
- `IP-CIDR,102.132.96.0/20,PROXY,no-resolve` → `ProxyIp: 102.132.96.0/20`
- `IP-CIDR,185.60.216.0/22,PROXY,no-resolve` → `ProxyIp: 185.60.216.0/22`
- `IP-CIDR,179.60.192.0/22,PROXY,no-resolve` → `ProxyIp: 179.60.192.0/22`
- `IP-CIDR,31.13.24.0/21,PROXY,no-resolve` → `ProxyIp: 31.13.24.0/21`
- `IP-CIDR,66.220.144.0/20,PROXY,no-resolve` → `ProxyIp: 66.220.144.0/20`
- `IP-CIDR,69.63.176.0/20,PROXY,no-resolve` → `ProxyIp: 69.63.176.0/20`
- `IP-CIDR,69.171.224.0/19,PROXY,no-resolve` → `ProxyIp: 69.171.224.0/19`
- `IP-CIDR,74.119.76.0/22,PROXY,no-resolve` → `ProxyIp: 74.119.76.0/22`
- `IP-CIDR,129.134.0.0/16,PROXY,no-resolve` → `ProxyIp: 129.134.0.0/16`
- `IP-CIDR,157.240.0.0/16,PROXY,no-resolve` → `ProxyIp: 157.240.0.0/16`
- `IP-CIDR,173.252.64.0/18,PROXY,no-resolve` → `ProxyIp: 173.252.64.0/18`
- `IP-CIDR,93.186.225.194/32,DIRECT,no-resolve` → `DirectIp: 93.186.225.194/32`
- `IP-CIDR,17.0.0.0/8,DIRECT,no-resolve` → `DirectIp: 17.0.0.0/8`
- `IP-CIDR6,2403:300::/32,DIRECT,no-resolve` → `DirectIp: 2403:300::/32`
- `IP-CIDR6,2620:149::/32,DIRECT,no-resolve` → `DirectIp: 2620:149::/32`
- `IP-CIDR6,2a01:b740::/32,DIRECT,no-resolve` → `DirectIp: 2a01:b740::/32`
- `IP-CIDR,176.235.29.0/24,DIRECT,no-resolve` → `DirectIp: 176.235.29.0/24`
- `IP-CIDR,176.235.227.0/24,DIRECT,no-resolve` → `DirectIp: 176.235.227.0/24`
- `IP-CIDR,188.225.31.197/32,DIRECT,no-resolve` → `DirectIp: 188.225.31.197/32`
- `IP-CIDR,5.61.89.166/32,DIRECT,no-resolve` → `DirectIp: 5.61.89.166/32`
- `IP-CIDR,46.174.49.29/32,DIRECT,no-resolve` → `DirectIp: 46.174.49.29/32`

## Other intentionally-not-ported items

- `skip-proxy: localhost` — Shadowrocket skip-proxy hostname/wildcard semantics have no documented 1:1 INCY field; several tokens are also covered by Unified.
- `skip-proxy: *.local` — Shadowrocket skip-proxy hostname/wildcard semantics have no documented 1:1 INCY field; several tokens are also covered by Unified.
- `skip-proxy: captive.apple.com` — Shadowrocket skip-proxy hostname/wildcard semantics have no documented 1:1 INCY field; several tokens are also covered by Unified.
- `skip-proxy: *.ru` — Shadowrocket skip-proxy hostname/wildcard semantics have no documented 1:1 INCY field; several tokens are also covered by Unified.
- `skip-proxy: *.su` — Shadowrocket skip-proxy hostname/wildcard semantics have no documented 1:1 INCY field; several tokens are also covered by Unified.
- `skip-proxy: *.рф` — Shadowrocket skip-proxy hostname/wildcard semantics have no documented 1:1 INCY field; several tokens are also covered by Unified.
- `fallback-dns-server = https://freedns.controld.com/p0#proxy` — Standard INCY routing JSON documents one Remote DNS and one Domestic DNS, not a Remote-DNS fallback chain equivalent to Shadowrocket fallback-dns-server.
- Unified `[Host] server:system`: 293 entries are uniformly NOT PORTED because no documented per-domain System-DNS equivalent exists.

## Duplicate suppression

Count: **3**.
- `tun-excluded-routes: 10.0.0.0/8` → `DirectIp: 10.0.0.0/8`
- `tun-excluded-routes: 172.16.0.0/12` → `DirectIp: 172.16.0.0/12`
- `tun-excluded-routes: 192.168.0.0/16` → `DirectIp: 192.168.0.0/16`

## Potential cross-bucket overlaps requiring INCY E2E priority check

These are not declared errors: Shadowrocket resolves them by first-match/module order. INCY bucket precedence must be verified on-device before calling behavior equivalent.

### BlockSites ↔ DirectSites: 26

- `full:alt-ad.mail.ru` ↔ `domain:mail.ru`
- `full:alt-ad.mail.ru` ↔ `domain:ru`
- `full:ad.mail.ru` ↔ `domain:mail.ru`
- `full:ad.mail.ru` ↔ `domain:ru`
- `domain:target.my.com` ↔ `domain:my.com`
- `domain:advertising.my.com` ↔ `domain:my.com`
- `domain:tracker-api.vk-analytics.ru` ↔ `domain:ru`
- `domain:vk-analytics.ru` ↔ `domain:ru`
- `domain:tracker-api.my.com` ↔ `domain:my.com`
- `domain:top.mail.ru` ↔ `domain:mail.ru`
- `domain:top.mail.ru` ↔ `domain:ru`
- `full:r.mail.ru` ↔ `domain:mail.ru`
- `full:r.mail.ru` ↔ `domain:ru`
- `domain:an.yandex.ru` ↔ `domain:ru`
- `domain:mc.yandex.ru` ↔ `domain:ru`
- `domain:mc.yandex.com` ↔ `domain:yandex.com`
- `domain:metrika.yandex.ru` ↔ `domain:ru`
- `full:ads.adfox.ru` ↔ `domain:ru`
- `domain:adfox.yandex.ru` ↔ `domain:ru`
- `domain:adfstat.yandex.ru` ↔ `domain:ru`
- `domain:appmetrica.yandex.ru` ↔ `domain:ru`
- `domain:report.appmetrica.yandex.net` ↔ `domain:yandex.net`
- `domain:rosenberg.appmetrica.yandex.net` ↔ `domain:yandex.net`
- `domain:startup.mobile.yandex.net` ↔ `domain:yandex.net`
- `domain:market-baobab.yandex.ru` ↔ `domain:ru`
- `domain:market-click-baobab.yandex.ru` ↔ `domain:ru`

### BlockSites ↔ ProxySites: 1

- `full:ep2.facebook.com` ↔ `domain:facebook.com`

### DirectSites ↔ ProxySites: 1

- `domain:ru` ↔ `full:hermes.routelink.ru`

## Validation scope

Generator/tests can prove deterministic static conversion, source coverage and JSON validity. They do **not** prove INCY import, matcher interpretation, DNS behavior, bucket priority, autorouting delivery, subscription headers, or device E2E. Those belong to the later Sub-Store/INCY stage.

## Rollback

This stage does not alter canonical Shadowrocket policy or subscription delivery. Rollback is reverting/removing the INCY-only generator, generated `incy/` files, tests and INCY validation workflow. Existing Shadowrocket assets/URLs remain untouched.
