# SR-ALL-FILES-PROXY

Конфигурация Shadowrocket с раздельными глобальными настройками, маршрутизацией, выборочным System DNS и отдельным YouTube-модулем.

Публикация delivery-файлов идёт через валидные semver-теги GitHub и постоянный jsDelivr alias `@latest`. Workflow валидирует актуальный `main`, создаёт immutable semver tag, проверяет точную tagged-версию, purge'ит `@latest` и подтверждает byte-for-byte совпадение CDN с целевым состоянием.

## Ссылки для импорта

- Основной конфиг: https://cdn.jsdelivr.net/gh/Alexgood321/SR-ALL-FILES-PROXY@latest/config/remote.conf
- Unified Routing + System DNS: https://cdn.jsdelivr.net/gh/Alexgood321/SR-ALL-FILES-PROXY@latest/modules/Unified-Routing-System-DNS.sgmodule
- RU TLD + RU Non-RU DIRECT System DNS: https://cdn.jsdelivr.net/gh/Alexgood321/SR-ALL-FILES-PROXY@latest/modules/RU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule
- YouTube Module: https://cdn.jsdelivr.net/gh/Alexgood321/SR-ALL-FILES-PROXY@latest/modules/Youtube-Config.sgmodule

## Архитектура

- `config/remote.conf` — глобальные и базовые настройки, DNS, `GEOIP,RU,DIRECT` и `FINAL,PROXY`.
- `modules/Unified-Routing-System-DNS.sgmodule` — единая пользовательская маршрутизация DIRECT / PROXY / REJECT и перенесённые выборочные System DNS mappings.
- `modules/RU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule` — отдельные RU TLD и российские non-RU домены через DIRECT + System DNS.
- `modules/Youtube-Config.sgmodule` — отдельная YouTube-функциональность MITM / Rewrite / Script.
- `modules/youtube.response.js` — скрипт YouTube; его `raw.githubusercontent.com` URL не переводится на jsDelivr в рамках этой схемы.
