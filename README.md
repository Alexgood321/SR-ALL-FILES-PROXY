# SR-ALL-FILES-PROXY

Конфигурация Shadowrocket с раздельными слоями: базовый `remote.conf`, обязательная сервисная маршрутизация + выборочный System DNS, отдельная опциональная блокировка рекламы/трекеров и отдельный YouTube-модуль.

## Основная схема

Рекомендуемая базовая конфигурация:

1. `remote.conf` — глобальные параметры Shadowrocket, DNS по умолчанию, `GEOIP,RU,DIRECT` и `FINAL,PROXY`.
2. `Unified Routing + System DNS` — основная сервисная маршрутизация `DIRECT / PROXY` и выборочный `server:system` для нужных доменов.
3. `Ads + Privacy Block` — опциональный слой `REJECT` для рекламы, analytics и trackers. Если используется, модуль должен располагаться выше Unified по приоритету.
4. `YouTube Module` — отдельная специализированная функциональность MITM / Rewrite / Script; не является частью основной routing/DNS-схемы.

Для максимально стабильной базовой работы достаточно `remote.conf + Unified Routing + System DNS`. Ads/Privacy подключается отдельно только там, где нужна блокировка рекламы и трекеров.

## Постоянные ссылки для импорта

Эти URL используют `releases/latest/download/...` и предназначены оставаться стабильными между релизами:

- Основной конфиг: https://github.com/Alexgood321/SR-ALL-FILES-PROXY/releases/latest/download/remote.conf
- Unified Routing + System DNS: https://github.com/Alexgood321/SR-ALL-FILES-PROXY/releases/latest/download/Unified-Routing-System-DNS.sgmodule
- Ads + Privacy Block: https://github.com/Alexgood321/SR-ALL-FILES-PROXY/releases/latest/download/Ads-Privacy-Block.sgmodule
- YouTube Module: https://github.com/Alexgood321/SR-ALL-FILES-PROXY/releases/latest/download/Youtube-Config.sgmodule

Legacy / standalone вариант, который не нужно включать параллельно с Unified:

- RU TLD + RU Non-RU DIRECT System DNS: https://github.com/Alexgood321/SR-ALL-FILES-PROXY/releases/latest/download/RU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule

## Архитектура файлов

- `config/remote.conf` — глобальные и базовые настройки, DNS-схема, `GEOIP,RU,DIRECT` и `FINAL,PROXY`.
- `modules/Unified-Routing-System-DNS.sgmodule` — обязательный основной модуль сервисной маршрутизации `DIRECT / PROXY` + выборочный System DNS через `[Host]`. Рекламных/privacy `REJECT`-правил в нём нет.
- `modules/Ads-Privacy-Block.sgmodule` — отдельный опциональный модуль со всеми рекламными/privacy `REJECT`-правилами. При совместном использовании должен находиться выше Unified.
- `modules/RU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule` — legacy / standalone вариант RU TLD и российских non-RU доменов через DIRECT + System DNS. Его политика уже интегрирована в Unified, поэтому параллельно с Unified его включать не нужно.
- `modules/Youtube-Config.sgmodule` — отдельная YouTube-функциональность MITM / Rewrite / Script.
- `modules/youtube.response.js` — скрипт YouTube через `raw.githubusercontent.com`; он не входит в release delivery как отдельный `.sgmodule` asset.

## DNS и RU-маршрутизация

`remote.conf` задаёт глобальную DNS-базу. В Unified отдельные домены и группы доменов могут быть направлены на `server:system` через `[Host]`.

Для `.ru`, `.su` и `.рф` (`xn--p1ai`) в Unified используются одновременно:

- `DOMAIN-SUFFIX,...,DIRECT` в `[Rule]`;
- `server:system` в `[Host]`.

Правило `GEOIP,RU,DIRECT` находится в `remote.conf` и использует GeoIP-механику Shadowrocket.

## Delivery

Delivery публикуется в versioned GitHub Releases. Publication workflow:

- не изменяет содержимое репозитория и не делает commit/push;
- берёт стабильный `main` как источник delivery;
- публикует top-level `.sgmodule` assets и `remote.conf`;
- проверяет SHA256/размеры release assets;
- проверяет versioned download URL и постоянные `releases/latest/download/...` byte-for-byte против выбранного стабильного `main`.

Существующие production asset names и постоянные `releases/latest/download/...` URL нельзя менять без сознательной миграции, потому что они уже могут быть установлены на устройствах.

## Проверка изменений

Репозиторий содержит `scripts/validate_shadowrocket.py` для статической/семантической проверки основной конфигурации. Успешный validator и успешная публикация подтверждают только соответствующие статические и delivery-слои. Они не являются доказательством реального runtime/device поведения Shadowrocket; критичные изменения маршрутизации, DNS или модулей при необходимости проверяются отдельно на устройстве и по PacketTunnel-логам.
