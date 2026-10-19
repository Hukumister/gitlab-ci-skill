# Rules и workflow

## Содержание

- [Как устроен workflow](#как-устроен-workflow)
- [Сначала смотри, как устроено в проекте](#сначала-смотри-как-устроено-в-проекте)
- [Шаблоны правил: структура по умолчанию](#шаблоны-правил-структура-по-умолчанию)
- [Отдельный пайплайн на тип события](#отдельный-пайплайн-на-тип-события)
- [Типы пайплайнов через переменную (по запросу)](#типы-пайплайнов-через-переменную-по-запросу)
- [workflow:rules: какие события пускать](#workflowrules-какие-события-пускать)
- [Отмена устаревших пайплайнов](#отмена-устаревших-пайплайнов)
- [Семантика rules у джоб](#семантика-rules-у-джоб)
- [Частые условия](#частые-условия)
- [rules:changes и его ловушки](#ruleschanges-и-его-ловушки)
- [rules:exists и rules:variables](#rulesexists-и-rulesvariables)
- [Ручные джобы](#ручные-джобы)
- [Почему джоба не появилась](#почему-джоба-не-появилась)

В примерах ниже правила для краткости часто написаны прямо в джобе. В проекте оформляй их так, как там принято (см.
следующие разделы).

## Как устроен workflow

У проекта одна конфигурация CI: `.gitlab-ci.yml` вместе со всем, что подключено через `include`. Ключ `workflow` в
итоговой конфигурации один. На каждое событие (пуш, MR, тег, расписание, ручной запуск, триггер) GitLab:

1. собирает эту конфигурацию;
2. проверяет `workflow:rules` сверху вниз до первого совпадения; если совпадений нет, пайплайн не создаётся;
3. проверяет `rules` каждой джобы; в пайплайн попадают совпавшие.

Следствия, которые стоит проговорить пользователю, если он путается:

- Отдельного `workflow` на MR, релиз и ночной прогон, как файлов в `.github/workflows` у GitHub Actions, в GitLab нет.
  Разные «пайплайны» получаются из разных наборов джоб внутри одной конфигурации или из дочерних пайплайнов, у которых
  своя конфигурация.
- Если `workflow` задан и в подключённом файле, и в корневом, значения сливаются, а `workflow:rules` из корневого файла
  целиком заменяет подключённые.
- У дочернего пайплайна свой `workflow` (если он нужен) и свой `CI_PIPELINE_SOURCE` (`parent_pipeline`).

## Сначала смотри, как устроено в проекте

По умолчанию повторяй устройство, которое уже есть в проекте, даже если ниже описан другой вариант. Перед правкой
выясни:

- **Где живут условия запуска.** Прямо в джобах, в скрытых шаблонах (`.rules-*`, `.rules:*`, `.if-*` и т.п.), в
  отдельном файле (`.gitlab/ci/rules.yml`), в общем репозитории шаблонов (`include: project`) или в CI/CD-компонентах.
- **Как джобы их подключают.** Через `extends` или через `!reference`.
- **Разнесены ли типы пайплайнов** (MR, релиз, ночной) по отдельным файлам или дочерним пайплайнам (`trigger: include`).
- **Как называются** шаблоны, файлы и переменные.

С чего начать поиск:

```bash
git ls-files | grep -E '(^|/)\.gitlab-ci\.yml$|^\.gitlab/'
grep -rnE '^\.[A-Za-z0-9_:-]*(rules|if)[A-Za-z0-9_:-]*:' .gitlab-ci.yml .gitlab/
grep -rnE 'trigger:|include:|component:|!reference' .gitlab-ci.yml .gitlab/
```

Новые джобы подключай к существующим шаблонам правил. Если подходящего нет, добавь новый шаблон рядом с остальными, в
том же стиле именования. Структуру проекта попутно не переделывай: если видишь, что её стоит поменять, предложи это
одной строкой в ответе и делай только по просьбе.

## Шаблоны правил: структура по умолчанию

Если в проекте ещё нет устоявшейся структуры (новый проект или пайплайн пишется с нуля), выноси условия запуска в
именованные шаблоны в отдельном файле, по одному шаблону на событие. Готовый
файл: [assets/rules.yml](../assets/rules.yml).

```yaml
# .gitlab/ci/rules.yml
.rules-mr:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"

.rules-main:
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH && $CI_PIPELINE_SOURCE != "schedule"

.rules-release:
  rules:
    - if: $CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/

.rules-nightly:
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule" && $SCHEDULE_TYPE == "nightly"
```

Подключение:

```yaml
include:
  - local: .gitlab/ci/rules.yml

ui-tests-full:
  extends: .rules-nightly
  script:
    - ./scripts/ci/ui-tests.sh --full

unit-tests:
  rules:
    - !reference [ .rules-mr, rules ]
    - !reference [ .rules-main, rules ]
  script:
    - ./scripts/ci/unit-tests.sh
```

Что важно:

- **Одно событие** подключай через `extends`, **несколько** через `!reference` на каждый шаблон.
  `extends: [.rules-mr, .rules-main]` не объединяет условия: массивы при `extends` заменяются, и останутся только
  правила последнего шаблона.
- Частые комбинации можно оформить отдельным шаблоном (`.rules-mr-and-main`), который сам собран из `!reference`.
- К подтянутому через `!reference` правилу нельзя дописать `when: manual` или `allow_failure`. Для таких случаев заводи
  отдельный шаблон (`.rules-release-manual`) или пиши правило в джобе.
- Расписание запускается на ветке. Без `$CI_PIPELINE_SOURCE != "schedule"` шаблон основной ветки сработает и в ночном
  пайплайне, и туда приедут деплой и всё, что идёт на `main`.
- Разные расписания различай переменной, заданной в настройках расписания (`SCHEDULE_TYPE=nightly`), источник у всех
  один: `schedule`.
- Условия по изменённым файлам (`changes`) тоже удобно держать в шаблонах: `.rules-mr-frontend` с
  `changes: [frontend/**/*]`.
- `workflow:rules` должен пропускать ровно те события, под которые есть шаблоны (см. ниже).

## Отдельный пайплайн на тип события

Когда наборы джоб для MR, релиза и ночного прогона сильно различаются, каждый тип можно вынести в свой файл и запускать
дочерним пайплайном. Корневой файл тогда только решает, какой пайплайн нужен:

```yaml
# .gitlab-ci.yml
include:
  - local: .gitlab/ci/rules.yml

mr:
  extends: .rules-mr
  trigger:
    include: .gitlab/ci/mr.yml
    strategy: mirror

release:
  extends: .rules-release
  trigger:
    include: .gitlab/ci/release.yml
    strategy: mirror

nightly:
  extends: .rules-nightly
  trigger:
    include: .gitlab/ci/nightly.yml
    strategy: mirror
```

- Каждый дочерний файл читается как самостоятельный пайплайн со своими `stages`; правила по типу события внутри не нужны,
  файл и так запускается только для своего события.
- Внутри дочернего пайплайна `CI_PIPELINE_SOURCE` равен `parent_pipeline`, поэтому `.rules-mr` и подобные шаблоны там не
  сработают. MR-условие внутри дочернего пишется через `$CI_MERGE_REQUEST_ID`, а переменные расписания (`SCHEDULE_TYPE`)
  доходят до дочернего только с `trigger:forward:pipeline_variables: true`.
- Общие джобы (например, сборку) подключай в каждый дочерний файл через `include` общего шаблона.
- `strategy: mirror` нужен, чтобы статус и отчёты тестов дочернего пайплайна попадали в родителя и в MR; на старых
  версиях GitLab вместо него `depend`.
- Цена подхода: лишний уровень вложенности в UI и более сложная передача артефактов между родительским и дочерним
  пайплайном. Механика дочерних пайплайнов: [child-pipelines.md](child-pipelines.md).

## Типы пайплайнов через переменную (по запросу)

Используй этот вариант, только если пользователь сам просит или так уже устроено в проекте. `workflow` определяет тип
события и записывает его в переменную, джобы смотрят на тип:

```yaml
workflow:
  name: "$PIPELINE_TYPE · $CI_COMMIT_REF_NAME"
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      variables:
        PIPELINE_TYPE: mr
    - if: $CI_PIPELINE_SOURCE == "schedule" && $SCHEDULE_TYPE == "nightly"
      variables:
        PIPELINE_TYPE: nightly
    - if: $CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/
      variables:
        PIPELINE_TYPE: release
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      variables:
        PIPELINE_TYPE: main

unit-tests:
  rules:
    - if: $PIPELINE_TYPE =~ /^(mr|main|nightly)$/
  script:
    - ./scripts/ci/unit-tests.sh
```

Плюсы: классификация событий в одном месте, тип виден в имени пайплайна, матрица «джоба × тип» читается прямо из
`rules`. В `include:rules` переменная `PIPELINE_TYPE`, насколько известно, недоступна: `include` раскрывается раньше,
чем вычисляется `workflow`.

## workflow:rules: какие события пускать

`workflow:rules` решает, будет ли пайплайн вообще. Без него пуш в ветку с открытым MR создаёт два пайплайна, branch и
MR, и раннеры делают работу дважды.

Строгий вариант, согласованный с шаблонами правил: пайплайны только для MR, основной ветки, тегов и расписаний. Пуш в
ветку без MR ничего не запускает.

```yaml
workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
    - if: $CI_COMMIT_TAG
    - if: $CI_PIPELINE_SOURCE == "schedule"
```

Мягкий вариант: MR-пайплайн для веток с открытым MR, branch-пайплайн для остальных веток, плюс теги.

```yaml
workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH && $CI_OPEN_MERGE_REQUESTS
      when: never
    - if: $CI_COMMIT_BRANCH
    - if: $CI_COMMIT_TAG
```

Если пайплайн пропущен через `workflow`, но ни одна джоба не совпала, пайплайн не создаётся. Поэтому в мягком варианте
нужны джобы и для веток без MR, иначе разрешение в `workflow` ничего не даёт.

В MR-пайплайне переменная `$CI_COMMIT_BRANCH` не задана. Имя ветки там берут из `$CI_MERGE_REQUEST_SOURCE_BRANCH_NAME`
или `$CI_COMMIT_REF_NAME`.

`workflow:name` задаёт имя пайплайна в списке, удобно, чтобы отличать ночные и релизные запуски.

## Отмена устаревших пайплайнов

```yaml
workflow:
  auto_cancel:
    on_new_commit: interruptible

default:
  interruptible: true
```

- `on_new_commit: conservative` (значение по умолчанию) отменяет старый пайплайн, только пока в нём не стартовала ни
  одна джоба с `interruptible: false`.
- `on_new_commit: interruptible` отменяет только джобы с `interruptible: true`, остальные доезжают. Деплой с
  `interruptible: false` не прервётся, а тесты прервутся.
- `on_job_failure: all` отменяет остаток пайплайна при первом падении. Полезно для MR, где после красного unit-теста
  гонять UI-тесты бессмысленно.

`workflow:auto_cancel` есть только в свежих версиях GitLab. В старых используют настройку проекта «Auto-cancel redundant
pipelines» плюс `interruptible`.

## Семантика rules у джоб

- Правила проверяются сверху вниз, первое совпавшее решает всё: `when`, `allow_failure`, `variables`, `needs`.
- Если не совпало ни одно правило, джоба не добавляется в пайплайн.
- Правило без `if`, `changes` и `exists` совпадает всегда, его ставят последним как ветку «иначе».
- `when` по умолчанию `on_success`. `when: never` исключает джобу.
- В одной джобе нельзя смешивать `rules` и `only`/`except`.

```yaml
build:
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
      when: never
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  script:
    - ./scripts/ci/build.sh
```

## Частые условия

| Что                                  | Условие                                             |
|--------------------------------------|-----------------------------------------------------|
| MR-пайплайн                          | `$CI_PIPELINE_SOURCE == "merge_request_event"`      |
| основная ветка                       | `$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH`           |
| любой тег                            | `$CI_COMMIT_TAG`                                    |
| релизный тег                         | `$CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/`              |
| запуск по расписанию                 | `$CI_PIPELINE_SOURCE == "schedule"`                 |
| ручной запуск из UI                  | `$CI_PIPELINE_SOURCE == "web"`                      |
| запуск через API / trigger token     | `$CI_PIPELINE_SOURCE == "api"` / `"trigger"`        |
| дочерний пайплайн                    | `$CI_PIPELINE_SOURCE == "parent_pipeline"`          |
| пайплайн, запущенный другим проектом | `$CI_PIPELINE_SOURCE == "pipeline"`                 |
| MR в конкретную ветку                | `$CI_MERGE_REQUEST_TARGET_BRANCH_NAME == "release"` |
| у MR есть лейбл                      | `$CI_MERGE_REQUEST_LABELS =~ /run-e2e/`             |

Лейбл на MR удобен как ручной переключатель тяжёлых проверок: поставил `run-e2e`, перезапустил пайплайн, и e2e-джоба
появилась.

## rules:changes и его ловушки

```yaml
ui-tests:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes:
        - src/**/*
        - package-lock.json
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  script:
    - ./scripts/ci/ui-tests.sh
```

- В MR-пайплайне изменения считаются относительно целевой ветки MR, обычно это то, что нужно.
- В branch-пайплайне изменения считаются относительно предыдущего пуша. Для новой ветки и для пайплайнов без пуша
  (расписание, ручной запуск, API, триггер) `changes` всегда истинно, и тяжёлые джобы запустятся. Лечится через
  `compare_to` или использованием `changes` только в MR-правилах.
- Пути задаются glob-ом от корня репозитория; для вложенных файлов нужен `**`, например `src/**/*`.
- На основной ветке `changes` обычно не используют: там гоняют полный набор, чтобы ловить то, что пропустили в MR.
- Если `changes` есть у всех джоб MR-пайплайна, MR с изменениями «чужих» файлов (README, конфиги) останется без
  пайплайна. При «Pipelines must succeed» его нельзя будет смёржить. Пайплайн только из джоб `.pre`/`.post` тоже не
  запускается. Держи в MR хотя бы одну джобу без `changes` в обычной стадии; если подходящей проверки нет, подойдёт
  заглушка:

```yaml
mr-gate:
  stage: test
  image: alpine:3.20
  needs: []
  variables:
    GIT_STRATEGY: none
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  script:
    - echo "MR pipeline is not empty"
```

  Проверить, что MR-пайплайн не окажется пустым, можно скриптом `scripts/check_mr_pipeline_not_empty.py` (см.
  [testing.md](testing.md)).

```yaml
lint-docs:
  rules:
    - if: $CI_COMMIT_BRANCH
      changes:
        paths:
          - docs/**/*
        compare_to: refs/heads/main
  script:
    - ./scripts/ci/lint-docs.sh
```

## rules:exists и rules:variables

`exists` включает джобу, только если в репозитории есть файл. Удобно в общих шаблонах, которые подключают разные
проекты:

```yaml
docker-build:
  rules:
    - exists:
        - Dockerfile
  script:
    - ./scripts/ci/docker-build.sh
```

`variables` внутри правила задаёт переменные для конкретного условия:

```yaml
deploy:
  rules:
    - if: $CI_COMMIT_TAG
      variables:
        DEPLOY_ENV: production
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      variables:
        DEPLOY_ENV: staging
  script:
    - ./scripts/ci/deploy.sh "$DEPLOY_ENV"
```

## Ручные джобы

- `when: manual` внутри `rules` по умолчанию даёт `allow_failure: false`. Такая джоба блокирует пайплайн: следующие
  стадии ждут нажатия кнопки, статус пайплайна «blocked».
- `when: manual` на уровне джобы (без `rules`) по умолчанию даёт `allow_failure: true` и ничего не блокирует.
- Нужна необязательная кнопка внутри `rules`? Пиши `allow_failure: true` явно.

```yaml
publish-beta:
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      when: manual
      allow_failure: true
  script:
    - ./scripts/ci/publish.sh beta
```

## Почему джоба не появилась

Иди по порядку:

1. Пайплайн вообще создался? Если нет, проблема в `workflow:rules` или ни одна джоба не совпала. MR, который висит в
   «Checking pipeline status» и не мёржится, — частый признак именно этого: все джобы отсекли `changes`.
2. Какой у пайплайна источник (`CI_PIPELINE_SOURCE`)? Частая путаница между branch и MR-пайплайном: в MR-пайплайне нет
   `CI_COMMIT_BRANCH`, а в дочернем пайплайне источник `parent_pipeline`, и правила на `merge_request_event` там не
   срабатывают.
3. Пройди `rules` джобы сверху вниз и найди первое совпадение. Если правила подключены через `extends` с несколькими
   шаблонами, сработали только правила последнего.
4. Есть `changes` в branch-пайплайне без `compare_to`? Тогда на новой ветке он всегда истинен.
5. Ошибка «job needs X, but X is not in any previous stage» значит, что джоба из `needs` отфильтрована правилами.
   Согласуй правила или используй `needs: [{job: X, optional: true}]`.
6. Проверь на симуляции: `glab ci lint --dry-run --ref <ветка> --include-jobs` для пушей и тегов, `gitlab-ci-local --list`
   с переменными события для MR и расписаний. Итоговые правила после `extends` и `!reference` покажет
   `glab ci config compile` или `gitlab-ci-local --preview`. Подробности в [testing.md](testing.md).
