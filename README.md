# SR-ALL-FILES-PROXY

Актуальная конфигурация Shadowrocket с раздельными слоями: базовый `remote.conf`, обязательная сервисная маршрутизация + выборочный System DNS, отдельная опциональная блокировка рекламы/трекеров и отдельный YouTube-модуль. Production delivery публикуется через стабильные `releases/latest/download/...` URL.

## Что это за проект

Это не просто набор статических правил для Shadowrocket. Проект используется как постоянно поддерживаемая и проверяемая конфигурация маршрутизации, DNS и сетевых модулей для реальной эксплуатации на iPhone/iPad и других устройствах в разных сетях.

Основная работа проекта:

- поддерживать предсказуемую маршрутизацию `DIRECT / PROXY / REJECT` для конкретных сервисов, доменов, IP/CIDR и сетевых сценариев;
- разделять глобальную DNS-базу и выборочный System DNS там, где это действительно нужно для устойчивости конкретных сервисов;
- находить новые или изменившиеся домены, IP, CIDR, ASN, CDN/API/reachability endpoints и проверять, нужны ли они в production-правилах;
- проверять конфигурацию не только статически, но и по реальным `PacketTunnel`-логам устройств, чтобы понимать, какое правило, DNS-путь или модуль фактически сработал;
- отделять подтверждённый runtime от предположений: наличие правила в GitHub или release ещё не означает, что оно уже применилось и отработало на конкретном устройстве;
- сохранять стабильные production URL и модульную архитектуру, чтобы обновления можно было публиковать без переустановки конфигурации на устройствах.

Практический цикл проекта выглядит так: **наблюдение/мониторинг → проверка принадлежности и актуальности → сверка с текущими правилами → аккуратное изменение при необходимости → статическая/release-проверка → runtime-проверка по логам устройства**.

Цель проекта не в максимальном количестве правил. Приоритет — минимально необходимая, понятная и проверяемая политика без широких масок и случайных обходов, которые могут затронуть чужие сервисы.

## Быстрая установка в Shadowrocket

GitHub не делает `shadowrocket://` URL-Scheme обычной кликабельной ссылкой, поэтому кнопки ниже используют собственный HTTPS redirect этого репозитория через GitHub Pages и затем передают стабильный GitHub release URL в Shadowrocket.

| Компонент | Назначение | Добавить в Shadowrocket |
| --- | --- | --- |
| `remote.conf` | Базовая конфигурация, DNS, `GEOIP,RU,DIRECT`, `FINAL,PROXY` | [📥 Добавить конфиг](https://alexgood321.github.io/SR-ALL-FILES-PROXY/redirect.html?url=shadowrocket%3A%2F%2Fconfig%2Fadd%2Fhttps%3A%2F%2Fgithub.com%2FAlexgood321%2FSR-ALL-FILES-PROXY%2Freleases%2Flatest%2Fdownload%2Fremote.conf) |
| `Unified-Routing-System-DNS.sgmodule` | Основная сервисная маршрутизация `DIRECT / PROXY` + выборочный System DNS | [📥 Добавить модуль](https://alexgood321.github.io/SR-ALL-FILES-PROXY/redirect.html?url=shadowrocket%3A%2F%2Finstall%3Fmodule%3Dhttps%3A%2F%2Fgithub.com%2FAlexgood321%2FSR-ALL-FILES-PROXY%2Freleases%2Flatest%2Fdownload%2FUnified-Routing-System-DNS.sgmodule) |
| `Ads-Privacy-Block.sgmodule` | Опциональный `REJECT` для рекламы, analytics и trackers | [📥 Добавить модуль](https://alexgood321.github.io/SR-ALL-FILES-PROXY/redirect.html?url=shadowrocket%3A%2F%2Finstall%3Fmodule%3Dhttps%3A%2F%2Fgithub.com%2FAlexgood321%2FSR-ALL-FILES-PROXY%2Freleases%2Flatest%2Fdownload%2FAds-Privacy-Block.sgmodule) |
| `Youtube-Config.sgmodule` | Отдельная YouTube MITM / Rewrite / Script функциональность | [📥 Добавить модуль](https://alexgood321.github.io/SR-ALL-FILES-PROXY/redirect.html?url=shadowrocket%3A%2F%2Finstall%3Fmodule%3Dhttps%3A%2F%2Fgithub.com%2FAlexgood321%2FSR-ALL-FILES-PROXY%2Freleases%2Flatest%2Fdownload%2FYoutube-Config.sgmodule) |
| `RU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule` | Legacy / standalone RU routing + System DNS | [📥 Добавить legacy-модуль](https://alexgood321.github.io/SR-ALL-FILES-PROXY/redirect.html?url=shadowrocket%3A%2F%2Finstall%3Fmodule%3Dhttps%3A%2F%2Fgithub.com%2FAlexgood321%2FSR-ALL-FILES-PROXY%2Freleases%2Flatest%2Fdownload%2FRU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule) |

> `RU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule` не нужно включать параллельно с Unified: его политика уже интегрирована в Unified.
>
> Приватный Local Certificate Module намеренно не публикуется в этом репозитории.

## Основная схема

Рекомендуемая базовая конфигурация:

1. `remote.conf` — глобальные параметры Shadowrocket, DNS по умолчанию, `GEOIP,RU,DIRECT` и `FINAL,PROXY`.
2. `Unified Routing + System DNS` — основная сервисная маршрутизация `DIRECT / PROXY`, IP/CIDR service routing и выборочный `server:system` для нужных доменов.
3. `Ads + Privacy Block` — опциональный слой `REJECT` для рекламы, analytics и trackers. Если используется, модуль должен располагаться выше Unified по приоритету.
4. `YouTube Module` — отдельная специализированная функциональность MITM / Rewrite / Script; не является частью основной routing/DNS-схемы.

Для максимально стабильной базовой работы достаточно `remote.conf + Unified Routing + System DNS`. Ads/Privacy подключается отдельно только там, где нужна блокировка рекламы и трекеров.

## Постоянные ссылки для импорта

Эти URL используют `releases/latest/download/...` и предназначены оставаться стабильными между релизами:

- Основной конфиг: https://github.com/Alexgood321/SR-ALL-FILES-PROXY/releases/latest/download/remote.conf
- Unified Routing + System DNS: https://github.com/Alexgood321/SR-ALL-FILES-PROXY/releases/latest/download/Unified-Routing-System-DNS.sgmodule
- Ads + Privacy Block: https://github.com/Alexgood321/SR-ALL-FILES-PROXY/releases/latest/download/Ads-Privacy-Block.sgmodule
- YouTube Module: https://github.com/Alexgood321/SR-ALL-FILES-PROXY/releases/latest/download/Youtube-Config.sgmodule
- Legacy / standalone RU TLD + RU Non-RU DIRECT System DNS: https://github.com/Alexgood321/SR-ALL-FILES-PROXY/releases/latest/download/RU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule

## Архитектура файлов

- `config/remote.conf` — глобальные и базовые настройки, DNS-схема, `GEOIP,RU,DIRECT` и `FINAL,PROXY`.
- `modules/Unified-Routing-System-DNS.sgmodule` — обязательный основной модуль сервисной маршрутизации `DIRECT / PROXY`, IP/CIDR routing + выборочный System DNS через `[Host]`. Рекламных/privacy `REJECT`-правил в нём нет.
- `modules/Ads-Privacy-Block.sgmodule` — отдельный опциональный модуль со всеми рекламными/privacy `REJECT`-правилами. При совместном использовании должен находиться выше Unified.
- `modules/RU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule` — legacy / standalone вариант RU TLD и российских non-RU доменов через DIRECT + System DNS. Его политика уже интегрирована в Unified, поэтому параллельно с Unified его включать не нужно.
- `modules/Youtube-Config.sgmodule` — отдельная YouTube-функциональность MITM / Rewrite / Script.
- `modules/youtube.response.js` — внутренний скрипт YouTube через `raw.githubusercontent.com`; отдельно в Shadowrocket не устанавливается и не входит в release delivery как `.sgmodule` asset.

## DNS и RU-маршрутизация

`remote.conf` задаёт глобальную DNS-базу. В Unified отдельные домены и группы доменов могут быть направлены на `server:system` через `[Host]`.

Для `.ru`, `.su` и `.рф` (`xn--p1ai`) в Unified используются одновременно:

- `DOMAIN-SUFFIX,...,DIRECT` в `[Rule]`;
- `server:system` в `[Host]`.

Правило `GEOIP,RU,DIRECT` находится в `remote.conf` и использует GeoIP-механику Shadowrocket.

DNS-поведение в проекте рассматривается как часть общей routing-политики, а не как отдельная магическая таблица. Глобальный DNS задаётся базовым конфигом, а `server:system` применяется выборочно через Unified. Реальную последовательность резолвинга, retry/fallback и влияние конкретной сети мы подтверждаем по `PacketTunnel`-логам и не объявляем универсальным поведением Shadowrocket без runtime-доказательств.

## Delivery

Delivery публикуется в versioned GitHub Releases. Publication workflow:

- не изменяет содержимое репозитория и не делает commit/push;
- берёт стабильный `main` как источник delivery;
- публикует `remote.conf` и все top-level `modules/*.sgmodule` assets;
- проверяет SHA256/размеры release assets;
- проверяет versioned download URL и постоянные `releases/latest/download/...` byte-for-byte против выбранного стабильного `main`.

Существующие production asset names и постоянные `releases/latest/download/...` URL нельзя менять без сознательной миграции, потому что они уже могут быть установлены на устройствах.

## Проверка изменений

Репозиторий содержит `scripts/validate_shadowrocket.py` для статической/семантической проверки основной конфигурации. Успешный validator и успешная публикация подтверждают только соответствующие статические и delivery-слои. Они не являются доказательством реального runtime/device поведения Shadowrocket; критичные изменения маршрутизации, DNS или модулей при необходимости проверяются отдельно на устройстве и по PacketTunnel-логам.
