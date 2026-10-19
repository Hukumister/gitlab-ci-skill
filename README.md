# gitlab-ci-skill

Скиллы для ИИ-агентов по работе с GitLab CI/CD в формате [Agent Skills](https://agentskills.io): подходят для Claude
Code, opencode и других агентов, которые понимают `SKILL.md`. Статус: ранняя версия.

## Что внутри

```
skills/
└── gitlab-ci-pipelines/          # как проектировать и писать пайплайны
    ├── SKILL.md                  # точка входа: порядок работы, принципы, чеклист, формат ответа
    ├── references/               # подробности, Claude читает их по необходимости
    │   ├── rules-and-workflow.md # как устроен workflow, шаблоны правил, типы пайплайнов
    │   ├── jobs-and-dag.md       # needs, параллелизм, деплой, скрипты
    │   ├── child-pipelines.md    # дочерние и multi-project пайплайны
    │   ├── cache-and-artifacts.md
    │   ├── reuse.md              # default, extends, !reference, include: local
    │   ├── includes-and-components.md  # конфиги из других репозиториев, компоненты, версии
    │   ├── testing.md            # как проверять пайплайн
    │   ├── security.md
    │   └── anti-patterns.md      # для ревью и рефакторинга
    ├── assets/
    │   ├── base.gitlab-ci.yml    # стартовый шаблон пайплайна
    │   └── rules.yml             # шаблоны правил по событиям (.gitlab/ci/rules.yml)
    └── scripts/
        └── check_mr_pipeline_not_empty.py  # проверка, что MR-пайплайн не окажется пустым
```

## Что нужно

- [`glab`](https://gitlab.com/gitlab-org/cli), авторизованный на вашем инстансе по personal access token (scope `api`): `glab auth login --hostname <host>`. Без него скилл работает, но не может проверить конфиг через GitLab.
- [`gitlab-ci-local`](https://github.com/firecow/gitlab-ci-local) (сторонняя open-source утилита, MIT) и PyYAML для локальных проверок: какие джобы попадут в MR, ночной и релизный пайплайны и не окажется ли MR-пайплайн пустым. Без них скилл работает, но эти проверки пропускает.
- Контекст конкретного проекта (раннеры, раскладка, шаблоны правил) скилл берёт из AGENTS.md или CLAUDE.md проекта. Если раздела про CI там нет, после задачи он предложит дописать фрагмент с тем, что выяснил.

## Как подключить

### Через `npx skills`: Claude Code, opencode и другие агенты

[`skills`](https://github.com/vercel-labs/skills) — CLI, который ставит скиллы формата Agent Skills сразу в несколько
агентов. Нужен Node.js.

```bash
# для себя, во все проекты
npx skills add Hukumister/gitlab-ci-skill -s gitlab-ci-pipelines -a claude-code -a opencode -g

# в конкретный проект
npx skills add Hukumister/gitlab-ci-skill -s gitlab-ci-pipelines -a claude-code -a opencode

# конкретная версия
npx skills add Hukumister/gitlab-ci-skill#v0.1.0 -s gitlab-ci-pipelines -a claude-code -a opencode

# обновить: -g глобальные, -p проектные
npx skills update -g
```

- Установленный по тегу скилл `update` не сдвигает: чтобы перейти на новую версию, повтори `add` с новым тегом. Без тега
  ставится основная ветка, и `update` подтягивает новые коммиты.
- Основная копия ложится в `.agents/skills/gitlab-ci-pipelines` (с `-g` — в `~/.agents/skills/`), её читает opencode.
  Claude Code получает на неё симлинк в `.claude/skills/` (`~/.claude/skills/`). Флаг `--copy` ставит отдельные копии
  вместо симлинков.
- В проекте появляется `skills-lock.json`. Закоммить его вместе с `.agents/skills/` и `.claude/skills/`: коллеги получат
  скилл с репозиторием, а `npx skills update -p` будет знать, откуда обновляться.
- CLI отправляет события установки на skills.sh, установки публичных репозиториев попадают в его каталог. Отключается
  через `DISABLE_TELEMETRY=1` или `DO_NOT_TRACK=1`.

### Из своего GitLab

Если репозиторий зеркалируется во внутренний GitLab, ставить можно оттуда, команды те же:

```bash
DISABLE_TELEMETRY=1 npx skills add https://gitlab.example.com/group/gitlab-ci-skill.git -s gitlab-ci-pipelines -a claude-code -a opencode -g
```

- Адрес должен заканчиваться на `.git` или быть SSH-вида `git@gitlab.example.com:group/gitlab-ci-skill.git`. Без `.git`
  CLI принимает адрес за сайт и ищет скиллы через `/.well-known/`.
- Нужен git-доступ к репозиторию: SSH-ключ или сохранённый HTTPS-доступ.
- `DISABLE_TELEMETRY=1` здесь обязателен по смыслу: без него для путей длиннее `owner/repo` (например,
  `group/subgroup/repo`) на skills.sh уходит путь внутреннего репозитория.

### Для разработки скилла

Симлинк на рабочую копию, чтобы правки сразу подхватывались. opencode тоже читает `~/.claude/skills/`, так что одного
симлинка хватает обоим агентам:

```bash
mkdir -p ~/.claude/skills
ln -s "$PWD/skills/gitlab-ci-pipelines" ~/.claude/skills/gitlab-ci-pipelines
```

Новую версию для остальных выпускай тегом (`v0.1.0`, `v0.2.0`, `v1.0.0`), чтобы её можно было зафиксировать при установке.

### Приложение Claude

Заархивировать папку `skills/gitlab-ci-pipelines` в zip и загрузить в Settings → Capabilities → Skills. Шаги с glab и
`gitlab-ci-local` там пропускаются: в чате нет терминала.

## Дальше

- [ ] Прогнать на реальных задачах: новый пайплайн, ревью существующего, ускорение медленного
- [ ] Отдельный скилл для работы с запущенными пайплайнами (статусы, логи, ретраи через `glab`)

## Лицензия

MIT, см. [LICENSE](LICENSE).
