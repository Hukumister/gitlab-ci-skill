# Джобы и граф зависимостей

## Содержание

- [stages и needs](#stages-и-needs)
- [Параллелизм](#параллелизм)
- [Child и multi-project пайплайны](#child-и-multi-project-пайплайны)
- [Деплой и окружения](#деплой-и-окружения)
- [Надёжность: timeout, retry, allow_failure](#надёжность-timeout-retry-allow_failure)
- [Скрипты](#скрипты)
- [Git в джобах](#git-в-джобах)

## stages и needs

Стадии по умолчанию: `.pre`, `build`, `test`, `deploy`, `.post`. Джоба без `stage` попадает в `test`.

Без `needs` джоба ждёт, пока закончатся все джобы предыдущих стадий. С `needs` она стартует, как только закончились
перечисленные джобы, и скачивает артефакты только от них. `needs: []` означает «старт сразу».

```yaml
stages: [ check, build, test, deploy ]

lint:
  stage: check
  needs: [ ]
  script:
    - ./scripts/ci/lint.sh

build:
  stage: build
  needs: [ ]
  script:
    - ./scripts/ci/build.sh
  artifacts:
    paths:
      - build/output/
    expire_in: 1 day

unit-tests:
  stage: test
  needs: [ ]
  script:
    - ./scripts/ci/unit-tests.sh

integration-tests:
  stage: test
  needs: [ build ]
  script:
    - ./scripts/ci/integration-tests.sh

deploy-staging:
  stage: deploy
  needs: [ lint, build, unit-tests, integration-tests ]
  script:
    - ./scripts/ci/deploy.sh staging
```

Стадии здесь только группируют джобы в UI, порядок выполнения определяет `needs`.

Тонкая настройка зависимостей:

```yaml
report:
  needs:
    - job: build
      artifacts: true
    - job: lint
      artifacts: false
    - job: ui-tests
      optional: true
  script:
    - ./scripts/ci/report.sh
```

- `artifacts: false` ждёт джобу, но не скачивает её артефакты.
- `optional: true` не ломает создание пайплайна, если джоба отфильтрована правилами.
- У количества `needs` на одну джобу есть лимит (по умолчанию 50). Если упираешься в него, добавь агрегирующую джобу.

## Параллелизм

Шардирование тестов: GitLab запускает N копий джобы и передаёт `CI_NODE_INDEX` и `CI_NODE_TOTAL`.

```yaml
unit-tests:
  parallel: 4
  script:
    - ./scripts/ci/unit-tests.sh --shard "$CI_NODE_INDEX/$CI_NODE_TOTAL"
```

Матрица: по джобе на каждую комбинацию значений.

```yaml
build:
  parallel:
    matrix:
      - PLATFORM: [ linux-amd64, linux-arm64 ]
        PROFILE: [ debug, release ]
  script:
    - ./scripts/ci/build.sh "$PLATFORM" "$PROFILE"
  artifacts:
    paths:
      - build/outputs/
    expire_in: 1 day

publish-arm64-release:
  needs:
    - job: build
      parallel:
        matrix:
          - PLATFORM: linux-arm64
            PROFILE: release
  script:
    - ./scripts/ci/publish.sh
```

## Child и multi-project пайплайны

Когда нужен дочерний или multi-project пайплайн, как передавать в него переменные и артефакты, как писать правила
внутри дочернего пайплайна и как его отлаживать, описано в [child-pipelines.md](child-pipelines.md).

## Деплой и окружения

```yaml
deploy-production:
  stage: deploy
  needs: [ build ]
  interruptible: false
  resource_group: production
  environment:
    name: production
    url: https://example.com
  rules:
    - if: $CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/
      when: manual
  script:
    - ./scripts/ci/deploy.sh production
```

- `resource_group` гарантирует, что одновременно выполняется не больше одной джобы из группы, параллельные деплои в одно
  окружение исключены.
- `environment` даёт историю деплоев, откат и защищённые окружения.
- `interruptible: false`: новый коммит не должен прерывать деплой на середине.

Временные окружения для MR (review apps):

```yaml
review-deploy:
  environment:
    name: review/$CI_COMMIT_REF_SLUG
    on_stop: review-stop
    auto_stop_in: 3 days
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  script:
    - ./scripts/ci/review-deploy.sh

review-stop:
  environment:
    name: review/$CI_COMMIT_REF_SLUG
    action: stop
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      when: manual
      allow_failure: true
  script:
    - ./scripts/ci/review-stop.sh
```

## Надёжность: timeout, retry, allow_failure

```yaml
default:
  timeout: 30m
  retry:
    max: 2
    when:
      - runner_system_failure
      - api_failure
```

- `timeout` ставь под реальное время джобы с запасом. Без него зависшая джоба занимает раннер до лимита проекта (часто
  час).
- `retry` без `when` перезапускает и при падении теста, флаки становятся невидимыми, а время пайплайна удваивается.
  Перезапускай только по инфраструктурным причинам. В свежих версиях есть `retry:exit_codes` для конкретных кодов выхода
  (например, 137 при OOM).
- `allow_failure: true` прячет красные джобы. Если джоба может завершиться «с предупреждением», договорись о коде
  выхода:

```yaml
dependency-check:
  allow_failure:
    exit_codes: [ 42 ]
  script:
    - ./scripts/ci/dependency-check.sh   # 42 = есть устаревшие зависимости
```

## Скрипты

- `before_script` и `script` выполняются в одной shell-сессии. `after_script` выполняется в отдельной: переменные,
  экспортированные в `script`, там не видны, а падение `after_script` не меняет статус джобы. Используй его для уборки и
  сбора диагностики.
- Многострочные команды пиши блоком `|`:

```yaml
prepare:
  script:
    - |
      if [ -n "$CI_COMMIT_TAG" ]; then
        ./scripts/ci/prepare-release.sh "$CI_COMMIT_TAG"
      fi
```

- Строки, где есть `: ` или которые начинаются с `*`, `{`, `[`, `&`, `!`, `%`, `@`, бери в кавычки, иначе YAML прочитает
  их по-своему.
- Пайпы (`cmd | tee log`) возвращают код последней команды. Логику с пайпами выноси в скрипт с `set -euo pipefail`.
- Длинный лог удобно сворачивать секциями:

```yaml
build:
  script:
    - echo -e "\e[0Ksection_start:$(date +%s):deps[collapsed=true]\r\e[0KУстановка зависимостей"
    - ./scripts/ci/install-deps.sh
    - echo -e "\e[0Ksection_end:$(date +%s):deps\r\e[0K"
    - ./scripts/ci/build.sh
```

## Git в джобах

- По умолчанию клон неглубокий (`GIT_DEPTH`). Если инструменту нужна история (версия из тегов, diff с основной веткой),
  увеличь глубину для этой джобы или дотяни нужное через `git fetch`.
- `GIT_STRATEGY: none` пропускает получение репозитория. Подходит джобам, которым нужны только артефакты; скриптов из
  репозитория у такой джобы тоже не будет.
- `GIT_SUBMODULE_STRATEGY: recursive` нужен, только если сабмодули действительно используются в джобе.
