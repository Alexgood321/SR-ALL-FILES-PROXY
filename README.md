# SR-ALL-FILES-PROXY

Конфигурация Shadowrocket с раздельными глобальными настройками, маршрутизацией, выборочным System DNS и отдельным YouTube-модулем.

## Ссылки для импорта

- Основной конфиг: https://cdn.jsdelivr.net/gh/Alexgood321/SR-ALL-FILES-PROXY@main/config/remote.conf
- Unified Routing + System DNS: https://cdn.jsdelivr.net/gh/Alexgood321/SR-ALL-FILES-PROXY@main/modules/Unified-Routing-System-DNS.sgmodule
- RU TLD + RU Non-RU DIRECT System DNS: https://cdn.jsdelivr.net/gh/Alexgood321/SR-ALL-FILES-PROXY@main/modules/RU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule
- YouTube Module: https://cdn.jsdelivr.net/gh/Alexgood321/SR-ALL-FILES-PROXY@main/modules/Youtube-Config.sgmodule

## Архитектура

- `config/remote.conf` — глобальные и базовые настройки, DNS, `GEOIP,RU,DIRECT` и `FINAL,PROXY`.
- `modules/Unified-Routing-System-DNS.sgmodule` — единая пользовательская маршрутизация DIRECT / PROXY / REJECT и перенесённые выборочные System DNS mappings.
- `modules/RU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule` — отдельные RU TLD и российские non-RU домены через DIRECT + System DNS.
- `modules/Youtube-Config.sgmodule` — отдельная YouTube-функциональность MITM / Rewrite / Script.
- `modules/youtube.response.js` — скрипт YouTube через `raw.githubusercontent.com`; он не входит в CDN delivery workflow.
