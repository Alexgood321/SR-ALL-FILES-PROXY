# SR-ALL-FILES-PROXY

Конфигурация Shadowrocket с раздельными глобальными настройками, маршрутизацией, выборочным System DNS и отдельным YouTube-модулем.

Delivery публикуется как immutable GitHub Release assets. Постоянные ссылки используют официальный `releases/latest/download/...` redirect и после каждого релевантного push проверяются byte-for-byte против стабильного `main`.

## Ссылки для импорта

- Основной конфиг: https://github.com/Alexgood321/SR-ALL-FILES-PROXY/releases/latest/download/remote.conf
- Unified Routing + System DNS: https://github.com/Alexgood321/SR-ALL-FILES-PROXY/releases/latest/download/Unified-Routing-System-DNS.sgmodule
- RU TLD + RU Non-RU DIRECT System DNS: https://github.com/Alexgood321/SR-ALL-FILES-PROXY/releases/latest/download/RU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule
- YouTube Module: https://github.com/Alexgood321/SR-ALL-FILES-PROXY/releases/latest/download/Youtube-Config.sgmodule

## Архитектура

- `config/remote.conf` — глобальные и базовые настройки, DNS, `GEOIP,RU,DIRECT` и `FINAL,PROXY`.
- `modules/Unified-Routing-System-DNS.sgmodule` — единая пользовательская маршрутизация DIRECT / PROXY / REJECT и перенесённые выборочные System DNS mappings.
- `modules/RU-TLD-RU-Non-RU-DIRECT-System-DNS.sgmodule` — отдельные RU TLD и российские non-RU домены через DIRECT + System DNS.
- `modules/Youtube-Config.sgmodule` — отдельная YouTube-функциональность MITM / Rewrite / Script.
- `modules/youtube.response.js` — скрипт YouTube через `raw.githubusercontent.com`; он не входит в release delivery workflow.
