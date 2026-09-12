# INCY Full Xray conversion report

Static repository conversion only. It does not prove Sub-Store delivery or INCY device E2E.

## Source of truth

- `config/remote.conf` — SHA256 `78b60dd2c6a1c63ba863d07f56ee0035f747f5309a188d941e1ecf72059098d4`
- `modules/Unified-Routing-System-DNS.sgmodule` — SHA256 `dd6d66b2c222a1b8a53a3b8be26c6aac8908aa8b2228bfc8df9eaa04cea1d695`
- `modules/Ads-Privacy-Block.sgmodule` — SHA256 `2512e9115f9ec81fc52b8507e155c3aa8ddb501c74f511bd7a2676ad0fca8727`
- YouTube/MITM files: **not used**.

## Generated native policy

- `https://raw.githubusercontent.com/Alexgood321/SR-ALL-FILES-PROXY/main/incy/xray-policy.json`
- Routing rules: **471**
- Selective System DNS matchers: **292**
- Intended use: Sub-Store embeds this `dns` + `routing` into every INCY Full Xray server config.
- No `autorouting`, routing header or separate routing profile is produced by this artifact.
- Legacy `incy/incy-routing.json` remains compatibility/diagnostic only until Full Xray E2E.

## Native mapping

- DOMAIN → `full:`; DOMAIN-SUFFIX → `domain:`; DOMAIN-KEYWORD → `keyword:`.
- IP-CIDR/IP-CIDR6/GEOIP use native Xray `ip` matchers.
- AND(selector + PROTOCOL TCP/UDP) stays one rule with both conditions.
- PROCESS-NAME → native `process`, status **PLATFORM_DEPENDENT**.
- USER-AGENT → **NOT PORTED / REQUIRES E2E**; `attrs` is not treated as 1:1.
- Order: Ads BLOCK → DNS infrastructure guard → Unified source order → local/private DIRECT → GEOIP RU DIRECT → explicit FINAL PROXY.

## DNS architecture

Generated serial resolver topology:
1. selective domains: `localhost` System DNS → ControlD DoH; Cloudflare is excluded from that matched list;
2. ordinary domains: Cloudflare DoH → ControlD DoH;
3. non-local DoH is tagged `dns-internal` and routed to proxy; localhost remains local.
`queryStrategy=UseIPv4` is a DNS-level adaptation only, not a claim of full parity with Shadowrocket `ipv6=false` for every platform/outbound.
Shadowrocket's observed extra retry of the same System DNS is **not claimed as reproduced**.
DNS ARCHITECTURE: IMPLEMENTED STATICALLY. DNS PARITY: NOT TESTED.

## Status counts

- `CONFIRMED STATIC MAPPING`: 428
- `NOT PORTED / COVERAGE CHECK`: 6
- `NOT PORTED / REQUIRES E2E`: 2
- `PLATFORM_DEPENDENT`: 1
- `SEMANTIC ADAPTATION`: 334
- `SKIPPED AS DUPLICATE`: 3

## PLATFORM_DEPENDENT

- `PROCESS-NAME,WhatsApp,PROXY` — Xray process matching is native on Windows/Linux; INCY Android/iOS behavior requires platform E2E.

## NOT PORTED / REQUIRES E2E

- `USER-AGENT,TikTok*,PROXY` — **NOT PORTED / REQUIRES E2E** — Xray attrs is not a safe 1:1 USER-AGENT substitute for general HTTPS/app traffic.
- `USER-AGENT,WhatsApp*,PROXY` — **NOT PORTED / REQUIRES E2E** — Xray attrs is not a safe 1:1 USER-AGENT substitute for general HTTPS/app traffic.
- `skip-proxy: localhost` — **NOT PORTED / COVERAGE CHECK** — Non-CIDR skip-proxy scope is not widened here; canonical domain policy comes from Unified.
- `skip-proxy: *.local` — **NOT PORTED / COVERAGE CHECK** — Non-CIDR skip-proxy scope is not widened here; canonical domain policy comes from Unified.
- `skip-proxy: captive.apple.com` — **NOT PORTED / COVERAGE CHECK** — Non-CIDR skip-proxy scope is not widened here; canonical domain policy comes from Unified.
- `skip-proxy: *.ru` — **NOT PORTED / COVERAGE CHECK** — Non-CIDR skip-proxy scope is not widened here; canonical domain policy comes from Unified.
- `skip-proxy: *.su` — **NOT PORTED / COVERAGE CHECK** — Non-CIDR skip-proxy scope is not widened here; canonical domain policy comes from Unified.
- `skip-proxy: *.рф` — **NOT PORTED / COVERAGE CHECK** — Non-CIDR skip-proxy scope is not widened here; canonical domain policy comes from Unified.

## SEMANTIC ADAPTATION

- `amp-api-search-edge.apps.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `amp-api-edge.apps.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `amp-api.apps.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `api-edge.apps.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `api.apps.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `bag.itunes.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `sf-api-token-service.itunes.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `silverbullet-external-ats.itunes.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `silverbullet-external-ats.v.aaplimg.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apps.mzstatic.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apps.mzstatic.com.g.aaplimg.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `is1-ssl.mzstatic.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `tr.iadsdk.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `icloud.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.icloud.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `me.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.me.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `mac.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.mac.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apple.news = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.apple.news = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `appleusercontent.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.appleusercontent.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apps.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.apps.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `itunes.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.itunes.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `itunes.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.itunes.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `itunes-apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.itunes-apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `itunes-nocookie.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.itunes-nocookie.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `mzstatic.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.mzstatic.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `aaplimg.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.aaplimg.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `g.aaplimg.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.g.aaplimg.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `appsto.re = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.appsto.re = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `appstoreconnect.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.appstoreconnect.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `testflight.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.testflight.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `iadsdk.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.iadsdk.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `icloud-content.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.icloud-content.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `cdn-apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.cdn-apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apple-dns.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.apple-dns.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apple-mapkit.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.apple-mapkit.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `push.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.push.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `push-apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.push-apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `courier.push.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apple-cloudkit.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.apple-cloudkit.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `ess.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.ess.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `identity.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.identity.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `ids-apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.ids-apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `guzzoni.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.guzzoni.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `gc.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.gc.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `ls.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.ls.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `gs-loc.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.gs-loc.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `captive.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.captive.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `gdmf.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.gdmf.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `deviceenrollment.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.deviceenrollment.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `deviceservices-external.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.deviceservices-external.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `albert.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.albert.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `time.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.time.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `time-ios.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.time-ios.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `init.itunes.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.init.itunes.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `iphone-ld.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.iphone-ld.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `xp.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.xp.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `mesu.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.mesu.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `swcdn.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.swcdn.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `swdist.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.swdist.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `swdownload.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.swdownload.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `swquery.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.swquery.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `swscan.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.swscan.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `updates-http.cdn-apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.updates-http.cdn-apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `updates.cdn-apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `app-site-association.cdn-apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `app-site-association.networking.apple = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `appldnld.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.appldnld.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `appldnld.apple.com.edgesuite.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `ocsp.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.ocsp.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `ocsp2.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.ocsp2.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `valid.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.valid.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `certs.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `crl.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `appattest.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.appattest.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apps-marketplace.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.apps-marketplace.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `token.safebrowsing.apple = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apple-relay.cloudflare.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apple-relay.fastly-edge.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apple-relay.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `doh.dns.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `gateway.icloud.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `mask.icloud.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `mask-h2.icloud.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `mask-api.icloud.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `probe.icloud.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `pong.icloud.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `metrics.icloud.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apple-native-relay.apple.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vk.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vk.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vk.ru = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vkuserphoto.ru = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.userapi.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.mycdn.me = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vkuseraudio.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vk.link = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vk.link = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vk.me = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vk.me = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vkuseraudio.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vkuseraudio.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vkuserlive.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vkuserlive.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vkuserlive.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vkuserlive.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vkuservideo.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vkuservideo.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vkuservideo.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vkuservideo.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `tamtam.chat = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.tamtam.chat = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.mail.ru = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.my.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.cloud.mail.ru = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `ru = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.ru = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `su = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.su = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `xn--p1ai = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.xn--p1ai = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `my.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `yandex.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.yandex.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `yastatic.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.yastatic.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `yandex.st = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.yandex.st = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `2gis.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.2gis.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `dgis.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.dgis.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `wbstatic.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.wbstatic.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `x5static.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.x5static.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `emias.info = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.emias.info = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `avito.st = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.avito.st = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `sberbank.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.sberbank.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vtb.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vtb.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `alfabank.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.alfabank.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `sovcombank.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.sovcombank.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `tochka.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.tochka.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `okko.tv = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.okko.tv = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `premier.one = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.premier.one = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `pobeda.aero = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.pobeda.aero = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `lenta.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.lenta.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `alfabank.st = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.alfabank.st = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `yandex.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.yandex.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `shedevrum.ai = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.shedevrum.ai = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `shedevrum.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.shedevrum.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `sourcecraft.dev = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.sourcecraft.dev = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `tochka-tech.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.tochka-tech.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `edadeal.io = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.edadeal.io = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `taxsee.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.taxsee.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `bronevik.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.bronevik.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `moex.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.moex.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `okko.sport = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.okko.sport = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `fix-price.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.fix-price.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `korona.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.korona.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `bank131.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.bank131.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `chizhik.club = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.chizhik.club = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `okolo.app = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.okolo.app = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `yandex.cloud = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.yandex.cloud = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `yandexcloud.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.yandexcloud.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `clstorage.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.clstorage.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `static-storage.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.static-storage.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `tilda.cc = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.tilda.cc = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `kinescopecdn.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.kinescopecdn.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apple-livephotoskit.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.apple-livephotoskit.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `apzones.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.apzones.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `icloud.com.cn = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.icloud.com.cn = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `cp4.cloudflare.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `crl3.digicert.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `crl4.digicert.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `ocsp.digicert.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `ocsp.digicert.cn = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vkuser.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vkuser.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `userapi.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `mycdn.me = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `mvk.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.mvk.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vk-cdn.me = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vk-cdn.me = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vk-portal.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vk-portal.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vk.cc = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vk.cc = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vk-cdn.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vk-cdn.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vk-cdn.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vk-cdn.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vkvd.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vkvd.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vk.team = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.vk.team = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `vkuseraudio.net = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `ozonusercontent.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.ozonusercontent.com = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `postmypost.io = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `*.postmypost.io = server:system` — Mapped to native Xray priority DNS domains with localhost System DNS.
- `dns.tag=dns-internal` — Forces Cloudflare/ControlD internal DNS traffic through proxy without routing localhost System DNS into a loop.
- `IP-CIDR,62.60.230.167/32,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,31.77.158.107/32,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,91.108.4.0/22,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,91.108.8.0/22,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,91.108.12.0/22,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,91.108.16.0/22,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,91.108.20.0/22,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,91.108.56.0/22,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,91.105.192.0/23,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,95.161.64.0/20,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,149.154.160.0/20,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,185.76.151.0/24,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR6,2001:67c:4e8::/48,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR6,2001:b28:f23d::/48,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR6,2001:b28:f23f::/48,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR6,2001:b28:f23c::/48,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR6,2a0a:f280::/32,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `AND,((IP-CIDR6,2a03:2880::/32,no-resolve),(PROTOCOL,UDP)),PROXY` — Native Xray combines selector and network conditions in one field rule.
- `IP-CIDR,31.13.64.0/18,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,102.132.96.0/20,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,185.60.216.0/22,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,179.60.192.0/22,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,31.13.24.0/21,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,66.220.144.0/20,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,69.63.176.0/20,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,69.171.224.0/19,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,74.119.76.0/22,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,129.134.0.0/16,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,157.240.0.0/16,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,173.252.64.0/18,PROXY,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,93.186.225.194/32,DIRECT,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,17.0.0.0/8,DIRECT,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR6,2403:300::/32,DIRECT,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR6,2620:149::/32,DIRECT,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR6,2a01:b740::/32,DIRECT,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,176.235.29.0/24,DIRECT,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,176.235.227.0/24,DIRECT,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,188.225.31.197/32,DIRECT,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,5.61.89.166/32,DIRECT,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `IP-CIDR,46.174.49.29/32,DIRECT,no-resolve` — CIDR target is preserved; Shadowrocket no-resolve has no 1:1 Xray modifier under IPIfNonMatch.
- `FINAL,PROXY` — Explicit universal IP fallback preserves IPIfNonMatch/geoip evaluation; unresolved no-match still falls to first proxy outbound in Full Xray config.

## Not proved by this stage

- VLESS/Trojan/VMess server-link → proxy outbound conversion and credential preservation;
- Sub-Store fetch/cache/LKG/fail-safe; INCY headers/client detection;
- no separate Routing Profile in INCY UI; iOS/Android/Desktop routing/DNS runtime;
- HAPP and Shadowrocket regression.
These remain Alpha/Sub-Store E2E work and must not inherit PASS from repository CI.

## Rollback

Revert the native generator/tests/workflow/generated Xray artifacts. Canonical Shadowrocket files and existing client delivery remain untouched.
