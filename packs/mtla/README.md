# MTLA Project Pack

Этот pack задаёт конфигурацию рантайма для проекта MTLA.

## Что внутри

- `pack.yaml` — метаданные и версия.
- `routing.yaml` — локальные правила role mapping по group/topic.
- `prompts/system.md` — системный prompt для MTLA.
- `presets/model.yaml` — model/think presets.
- `guardrails.yaml` — ограничения и правила.
- `runbook.md` — короткий runbook по обновлению.

## Как обновлять

1. Меняйте нужный конфиг-файл внутри этого каталога.
2. Обновляйте `version` и `updated` в `pack.yaml`.
3. Прогоняйте unit tests на маршрутизацию pack'ов.
4. Обновление не требует правки core-кода: runtime читает конфиги из файлов.

