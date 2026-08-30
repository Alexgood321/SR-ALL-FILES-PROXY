# SR-ALL-FILES-PROXY

Конфигурация Shadowrocket с раздельными глобальными настройками, маршрутизацией и функциональным YouTube-модулем. Кэш jsDelivr очищается автоматически после реальных изменений `config/**` или `modules/**` в `main`.

## Ссылки для импорта

- Основной конфиг: https://cdn.jsdelivr.net/gh/Alexgood321/SR-ALL-FILES-PROXY@main/config/remote.conf
- Routing Module: https://cdn.jsdelivr.net/gh/Alexgood321/SR-ALL-FILES-PROXY@main/modules/Routing.sgmodule
- YouTube Module: https://cdn.jsdelivr.net/gh/Alexgood321/SR-ALL-FILES-PROXY@main/modules/Youtube-Config.sgmodule

## Архитектура

- `config/remote.conf` — глобальные и базовые настройки, DNS, `GEOIP` и `FINAL`.
- `modules/Routing.sgmodule` — единая пользовательская маршрутизация DIRECT / PROXY / REJECT.
- `modules/Youtube-Config.sgmodule` — отдельная YouTube-функциональность MITM / Rewrite / Script.
