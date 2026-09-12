# Отчёт конвертации INCY

Сформирован из текущей канонической production-политики Shadowrocket. Это только аудит статической конвертации, а не подтверждение поведения INCY на устройстве/runtime.

## Источники

- `config/remote.conf` — SHA256 `78b60dd2c6a1c63ba863d07f56ee0035f747f5309a188d941e1ecf72059098d4`
- `modules/Unified-Routing-System-DNS.sgmodule` — SHA256 `dd6d66b2c222a1b8a53a3b8be26c6aac8908aa8b2228bfc8df9eaa04cea1d695`
- `modules/Ads-Privacy-Block.sgmodule` — SHA256 `2512e9115f9ec81fc52b8507e155c3aa8ddb501c74f511bd7a2676ad0fca8727`
- Базовый commit официальной документации INCY: `ad467b959cd7c6157fd041416c260ab849a29a4f`
- Документация routing: https://docs.incy.cc/routing/
- Документация autorouting: https://docs.incy.cc/autorouting/
- YouTube module/script: **не используются как источники**.

## Сгенерированный профиль

- Публичный URL stage 2: `https://raw.githubusercontent.com/Alexgood321/SR-ALL-FILES-PROXY/main/incy/incy-routing.json`
- `GlobalProxy = true`: несовпавший трафик остаётся PROXY (`FINAL,PROXY`).
- `DomainStrategy = IPIfNonMatch`: сначала доменные правила, затем IP/GeoIP при отсутствии совпадения.
- Remote DNS: Cloudflare DoH из `remote.conf`.
- `DnsHosts = {}`: `server:system` не подменяется статическими hosts.
- `DomesticDNS*` отсутствуют: произвольный Google/Yandex/другой resolver не придумывается. Отсутствующие поля могут использовать defaults INCY и требуют проверки на устройстве.
- `RemoteDNSIP`, `Geoipurl`, `Geositeurl` отсутствуют: canonical policy не содержит значений, которые можно перенести без изменения поведения; неявно используются встроенные geo-данные INCY.
- `FakeDNS = false`.

### Количество элементов в результате

- `DirectSites`: 221
- `DirectIp`: 25
- `ProxySites`: 125
- `ProxyIp`: 29
- `BlockSites`: 59
- `BlockIp`: 0

### Количество по статусам конвертации

- `ADAPTED`: 406
- `INTENTIONALLY NOT PORTED`: 300
- `PORTED`: 5
- `PORTED WITH SEMANTIC GAP`: 50
- `SKIPPED AS DUPLICATE`: 3
- `UNSUPPORTED`: 12

## Семантические расхождения / паритет не заявляется

- Выборочный `[Host] server:system` (Selective `[Host] server:system`): **293 записей не перенесены 1:1**. INCY `DnsHosts` — статическое domain→IP, а не selector System DNS.
- Резервная DNS-цепочка (DNS fallback) Shadowrocket (`System DNS → retry → ControlD #proxy` или `Cloudflare #proxy → ControlD #proxy`) не имеет документированного эквивалента Remote-DNS fallback в стандартном INCY routing JSON.
- Domestic DNS в INCY глобален для direct-ресурсов; System DNS Shadowrocket выборочен. DNS parity **не заявляется**.
- `USER-AGENT`, `PROCESS-NAME`, `DOMAIN-KEYWORD`, логические `AND`/`PROTOCOL` не расширяются приблизительными доменными правилами.
- `no-resolve` не имеет отдельного стандартного поля INCY. CIDR переносится, но DNS-trigger semantics при `IPIfNonMatch` требует E2E.
- Точное `DOMAIN` адаптируется в `full:...`, `DOMAIN-SUFFIX` — в `domain:...` (Exact `DOMAIN` is adapted), чтобы сохранить Xray-style область. Документация INCY допускает конкретные домены/категории, но явно не описывает эти префиксы на странице routing-профиля, поэтому нужен client E2E.
- `tun-excluded-routes` не имеет 1:1 routing-эквивалента: Shadowrocket выводит сеть за пределы TUN, а INCY DirectIp только направляет её DIRECT внутри клиента.
- `geoip:ru` использует встроенные geo-данные INCY; паритет GeoIP dataset с Shadowrocket не подтверждён.
- First-match/module priority Shadowrocket не считается автоматически эквивалентным bucket priority INCY.

## Неподдерживаемые правила Shadowrocket

Ни одно активное неподдерживаемое `[Rule]` не расширяется; все такие правила перечислены ниже.

| Исходное правило | Эквивалент INCY | Статус | Причина | Возможный эффект |
|---|---|---|---|---|
| `USER-AGENT,TikTok*,PROXY` | `NONE` | **UNSUPPORTED** | Стандартный routing-профиль INCY не документирует селектор USER-AGENT. | Правило пропускается, а не заменяется приблизительным аналогом. |
| `DOMAIN-KEYWORD,tiktok,PROXY` | `NONE` | **UNSUPPORTED** | Документация INCY routing не описывает эквивалент Shadowrocket DOMAIN-KEYWORD; преобразование в domain/suffix изменило бы область действия. | Правило пропускается, а не заменяется приблизительным аналогом. |
| `DOMAIN-KEYWORD,-tiktokcdn-com,PROXY` | `NONE` | **UNSUPPORTED** | Документация INCY routing не описывает эквивалент Shadowrocket DOMAIN-KEYWORD; преобразование в domain/suffix изменило бы область действия. | Правило пропускается, а не заменяется приблизительным аналогом. |
| `DOMAIN-KEYWORD,musical.ly,PROXY` | `NONE` | **UNSUPPORTED** | Документация INCY routing не описывает эквивалент Shadowrocket DOMAIN-KEYWORD; преобразование в domain/suffix изменило бы область действия. | Правило пропускается, а не заменяется приблизительным аналогом. |
| `PROCESS-NAME,WhatsApp,PROXY` | `NONE` | **UNSUPPORTED** | Стандартный routing-профиль INCY не документирует селектор PROCESS-NAME. | Правило пропускается, а не заменяется приблизительным аналогом. |
| `USER-AGENT,WhatsApp*,PROXY` | `NONE` | **UNSUPPORTED** | Стандартный routing-профиль INCY не документирует селектор USER-AGENT. | Правило пропускается, а не заменяется приблизительным аналогом. |
| `AND,((DOMAIN-SUFFIX,v.whatsapp.net),(PROTOCOL,UDP)),PROXY` | `NONE` | **UNSUPPORTED** | Стандартный routing-профиль INCY не документирует логические/PROTOCOL-селекторы Shadowrocket; упрощение расширило бы политику. | Правило пропускается, а не заменяется приблизительным аналогом. |
| `AND,((DOMAIN-SUFFIX,mmg.whatsapp.net),(PROTOCOL,UDP)),PROXY` | `NONE` | **UNSUPPORTED** | Стандартный routing-профиль INCY не документирует логические/PROTOCOL-селекторы Shadowrocket; упрощение расширило бы политику. | Правило пропускается, а не заменяется приблизительным аналогом. |
| `AND,((DOMAIN-SUFFIX,media.whatsapp.net),(PROTOCOL,UDP)),PROXY` | `NONE` | **UNSUPPORTED** | Стандартный routing-профиль INCY не документирует логические/PROTOCOL-селекторы Shadowrocket; упрощение расширило бы политику. | Правило пропускается, а не заменяется приблизительным аналогом. |
| `AND,((IP-CIDR6,2a03:2880::/32,no-resolve),(PROTOCOL,UDP)),PROXY` | `NONE` | **UNSUPPORTED** | Стандартный routing-профиль INCY не документирует логические/PROTOCOL-селекторы Shadowrocket; упрощение расширило бы политику. | Правило пропускается, а не заменяется приблизительным аналогом. |
| `DOMAIN-KEYWORD,jumpdesktop,PROXY` | `NONE` | **UNSUPPORTED** | Документация INCY routing не описывает эквивалент Shadowrocket DOMAIN-KEYWORD; преобразование в domain/suffix изменило бы область действия. | Правило пропускается, а не заменяется приблизительным аналогом. |
| `DOMAIN-KEYWORD,radiorecord,DIRECT` | `NONE` | **UNSUPPORTED** | Документация INCY routing не описывает эквивалент Shadowrocket DOMAIN-KEYWORD; преобразование в domain/suffix изменило бы область действия. | Правило пропускается, а не заменяется приблизительным аналогом. |

## Перенесённые CIDR с семантическим расхождением `no-resolve`

Количество: **39**. Направление маршрута сохранено, сам модификатор Shadowrocket `no-resolve` — нет.

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

## `tun-excluded-routes`: семантическая адаптация

Количество уникальных CIDR, перенесённых как DirectIp с semantic gap: **11**.
Shadowrocket исключает эти сети из TUN, тогда как стандартный INCY routing-профиль может только направить их DIRECT внутри клиента. Полный TUN parity не заявляется.

- `tun-excluded-routes: 100.64.0.0/10` → `DirectIp: 100.64.0.0/10`
- `tun-excluded-routes: 127.0.0.0/8` → `DirectIp: 127.0.0.0/8`
- `tun-excluded-routes: 169.254.0.0/16` → `DirectIp: 169.254.0.0/16`
- `tun-excluded-routes: 192.0.0.0/24` → `DirectIp: 192.0.0.0/24`
- `tun-excluded-routes: 192.0.2.0/24` → `DirectIp: 192.0.2.0/24`
- `tun-excluded-routes: 192.88.99.0/24` → `DirectIp: 192.88.99.0/24`
- `tun-excluded-routes: 198.51.100.0/24` → `DirectIp: 198.51.100.0/24`
- `tun-excluded-routes: 203.0.113.0/24` → `DirectIp: 203.0.113.0/24`
- `tun-excluded-routes: 224.0.0.0/4` → `DirectIp: 224.0.0.0/4`
- `tun-excluded-routes: 255.255.255.255/32` → `DirectIp: 255.255.255.255/32`
- `tun-excluded-routes: 239.255.255.250/32` → `DirectIp: 239.255.255.250/32`

## Остальные намеренно не перенесённые элементы

- `skip-proxy: localhost` — Для hostname/wildcard из Shadowrocket skip-proxy нет документированного 1:1 поля INCY; часть токенов дополнительно покрывается Unified.
- `skip-proxy: *.local` — Для hostname/wildcard из Shadowrocket skip-proxy нет документированного 1:1 поля INCY; часть токенов дополнительно покрывается Unified.
- `skip-proxy: captive.apple.com` — Для hostname/wildcard из Shadowrocket skip-proxy нет документированного 1:1 поля INCY; часть токенов дополнительно покрывается Unified.
- `skip-proxy: *.ru` — Для hostname/wildcard из Shadowrocket skip-proxy нет документированного 1:1 поля INCY; часть токенов дополнительно покрывается Unified.
- `skip-proxy: *.su` — Для hostname/wildcard из Shadowrocket skip-proxy нет документированного 1:1 поля INCY; часть токенов дополнительно покрывается Unified.
- `skip-proxy: *.рф` — Для hostname/wildcard из Shadowrocket skip-proxy нет документированного 1:1 поля INCY; часть токенов дополнительно покрывается Unified.
- `fallback-dns-server = https://freedns.controld.com/p0#proxy` — Стандартный INCY routing JSON документирует один Remote DNS и один Domestic DNS, но не цепочку Remote-DNS fallback, эквивалентную Shadowrocket fallback-dns-server.
- Unified `[Host] server:system`: 293 записей единообразно имеют статус NOT PORTED, поскольку документированного per-domain System-DNS эквивалента нет.

## Подавление дубликатов

Количество: **3**.
- `tun-excluded-routes: 10.0.0.0/8` → `DirectIp: 10.0.0.0/8`
- `tun-excluded-routes: 172.16.0.0/12` → `DirectIp: 172.16.0.0/12`
- `tun-excluded-routes: 192.168.0.0/16` → `DirectIp: 192.168.0.0/16`

## Возможные пересечения bucket, требующие проверки приоритета INCY E2E

Это не объявляется ошибкой: Shadowrocket разрешает пересечения через first-match/module order. Приоритет bucket INCY нужно проверить на устройстве до утверждения эквивалентности поведения.

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

## Область подтверждения

Генератор и тесты подтверждают детерминированную статическую конвертацию, покрытие источников и валидность JSON. Они **не подтверждают импорт INCY** (`do **not** prove INCY import`), трактовку matcher, DNS runtime, bucket priority, autorouting delivery, subscription headers или device E2E. Это относится к последующему этапу Sub-Store/INCY.

## Откат (Rollback)

Этот этап не меняет canonical Shadowrocket policy или delivery подписок. Откат — revert/remove INCY-only генератора, generated-файлов `incy/`, тестов и INCY validation workflow. Существующие Shadowrocket assets/URL остаются без изменений.
