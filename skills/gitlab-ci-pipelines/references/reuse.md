# Переиспользование конфигурации

## Содержание

- [Что выбрать](#что-выбрать)
- [default](#default)
- [extends](#extends)
- [!reference](#reference)
- [YAML-якоря](#yaml-якоря)
- [include: local](#include-local)
- [Где задавать переменные](#где-задавать-переменные)

## Что выбрать

| Нужно                                               | Инструмент                                                                                     |
|-----------------------------------------------------|------------------------------------------------------------------------------------------------|
| общие настройки для всех джоб                       | `default`                                                                                      |
| несколько похожих джоб в одном файле                | скрытая джоба `.name` + `extends`                                                              |
| взять отдельный кусок (список команд, набор правил) | `!reference`                                                                                   |
| разнести большой файл на части                      | `include: local`                                                                               |
| общие шаблоны для многих репозиториев               | `include: project` с `ref`, см. [includes-and-components.md](includes-and-components.md)       |
| переиспользуемый блок с параметрами и контрактом    | CI/CD-компонент со `spec:inputs`, см. [includes-and-components.md](includes-and-components.md) |

## default

```yaml
default:
  image: registry.example.com/ci/base:1.4.2
  tags: [ docker ]
  interruptible: true
  timeout: 20m
  retry:
    max: 2
    when: [ runner_system_failure, api_failure ]
```

- В `default` можно задать: `after_script`, `artifacts`, `before_script`, `cache`, `hooks`, `id_tokens`, `image`,
  `interruptible`, `retry`, `services`, `tags`, `timeout`.
- `variables` в `default` не поддерживается: глобальные переменные задаются на верхнем уровне файла.
- `image`, `services`, `cache`, `before_script`, `after_script` на верхнем уровне файла устарели, их место в `default`.
- Джоба может отказаться от наследования: `inherit: {default: false}` или `inherit: {default: [image]}`.

## extends

```yaml
.node-job:
  image: registry.example.com/ci/node:22.11.0
  tags: [ docker ]
  before_script:
    - npm ci

build-web:
  extends: .node-job
  script:
    - npm run build
```

- Словари сливаются рекурсивно, массивы (`script`, `rules`, `needs`, `tags`, `before_script`) заменяются целиком. Если в
  наследнике есть `rules`, родительские правила полностью отбрасываются.
- При нескольких родителях (`extends: [.a, .b]`) побеждает тот, что правее.
- Держи наследование в 2–3 уровня. Глубже уже трудно понять, что получилось в итоге.
- Посмотреть итоговую конфигурацию можно в Pipeline editor (вкладка Full configuration) или в поле `merged_yaml` ответа
  CI Lint API.

## !reference

Берёт конкретный ключ из другой джобы. Работает между файлами, подключёнными через `include`.

```yaml
.rules-mr:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"

.rules-main:
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH && $CI_PIPELINE_SOURCE != "schedule"

.setup:
  script:
    - ./scripts/ci/setup.sh

test:
  rules:
    - !reference [ .rules-mr, rules ]
    - !reference [ .rules-main, rules ]
  script:
    - !reference [ .setup, script ]
    - ./scripts/ci/test.sh
```

Вложенные списки разворачиваются автоматически, поэтому к подтянутым правилам и командам можно дописывать свои. Так же
собираются условия из нескольких шаблонов правил: через `extends` это не работает, там массив `rules` последнего шаблона
заменит остальные. Как организовать шаблоны правил, описано в [rules-and-workflow.md](rules-and-workflow.md).

Имена шаблонов, на которые ссылаешься через `!reference`, лучше писать без двоеточий: внутри `[...]` двоеточие может
сломать разбор YAML.

## YAML-якоря

`&anchor` и `<<: *anchor` работают только внутри одного файла: в файле, подключённом через `include`, якоря из другого
файла не видны. Для общих шаблонов используй `extends` и `!reference`.

## include: local

Свой большой файл раскладывай по частям в `.gitlab/ci/` и подключай из корневого:

```yaml
include:
  - local: .gitlab/ci/rules.yml
  - local: .gitlab/ci/backend.yml
```

- У `include` бывают свои `rules` (`if`, `exists`, `changes`) для условного подключения.
- Ключи из корневого файла переопределяют одноимённые ключи из подключённых (глубокое слияние, массивы заменяются
  целиком).

Подключение файлов из других репозиториев (`include: project`), CI/CD-компоненты, их версии, права доступа и проверка
изменений в общих шаблонах описаны в [includes-and-components.md](includes-and-components.md).

## Где задавать переменные

Приоритет от высокого к низкому (упрощённо):

1. Переменные пайплайна: ручной запуск, расписание, API, триггер.
2. CI/CD-переменные проекта, затем группы, затем инстанса (Settings → CI/CD → Variables).
3. Переменные из `dotenv`-отчётов.
4. `variables` джобы в YAML.
5. `variables` верхнего уровня в YAML.
6. Предопределённые переменные GitLab.

Следствие: значение из настроек проекта перекрывает значение из YAML. Если переменная «не меняется», проверь, не задана
ли она в настройках.

Для ручного запуска переменным верхнего уровня можно задать описание и список значений, они появятся в форме Run
pipeline:

```yaml
variables:
  DEPLOY_TARGET:
    value: staging
    options: [ staging, production ]
    description: Куда деплоить при ручном запуске
```
