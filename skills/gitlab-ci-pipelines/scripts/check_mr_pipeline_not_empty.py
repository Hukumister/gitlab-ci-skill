#!/usr/bin/env python3
"""Проверяет, что MR-пайплайн не окажется пустым при любом наборе изменённых файлов.

Худший случай для MR: изменённые файлы не совпали ни с одним шаблоном rules:changes.
Тогда правила с changes не срабатывают, и если других джоб нет, GitLab не создаёт
пайплайн. При включённой настройке «Pipelines must succeed» такой MR нельзя смёржить.
Пайплайн из одних джоб стадий .pre и .post тоже не запускается.

Скрипт берёт итоговую конфигурацию через `gitlab-ci-local --preview`, убирает из rules
все правила с changes (в худшем случае они не срабатывают) и через
`gitlab-ci-local --list-json` смотрит, какие джобы попадут в MR-пайплайн.

Запуск из корня репозитория. Нужны gitlab-ci-local и PyYAML. Новые файлы, подключаемые
через include: local, должны быть добавлены в git (`git add`), иначе gitlab-ci-local
их не увидит.

    python3 check_mr_pipeline_not_empty.py
    python3 check_mr_pipeline_not_empty.py --variable CI_MERGE_REQUEST_TARGET_BRANCH_NAME=develop

Коды выхода: 0 — в MR-пайплайне всегда будет хотя бы одна джоба; 1 — пайплайн может
оказаться пустым; 2 — проверку выполнить не удалось.
"""

import argparse
import json
import os
import subprocess
import sys

TOP_LEVEL_KEYWORDS = {
    "default", "include", "stages", "variables", "workflow", "spec",
    "image", "services", "cache", "before_script", "after_script",
}
EDGE_STAGES = {".pre", ".post"}
PROBE_FILE = ".gitlab-ci-mr-probe.yml"


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def without_changes(rules):
    kept = [r for r in rules if not (isinstance(r, dict) and "changes" in r)]
    return kept or [{"when": "never"}]


def make_worst_case(config):
    """Убирает условия changes; возвращает имена джоб, которые от них зависели."""
    depends_on_changes = []
    for name, job in config.items():
        if name in TOP_LEVEL_KEYWORDS or name.startswith(".") or not isinstance(job, dict):
            continue
        rules = job.get("rules")
        if isinstance(rules, list):
            if any(isinstance(r, dict) and "changes" in r for r in rules):
                depends_on_changes.append(name)
            job["rules"] = without_changes(rules)
        for key in ("only", "except"):
            if isinstance(job.get(key), dict) and "changes" in job[key]:
                depends_on_changes.append(name)
                job.pop("only", None)
                job.pop("except", None)
                job["rules"] = [{"when": "never"}]
                break
    workflow = config.get("workflow")
    if isinstance(workflow, dict) and isinstance(workflow.get("rules"), list):
        workflow["rules"] = without_changes(workflow["rules"])
    return depends_on_changes


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file", default=".gitlab-ci.yml", help="корневой файл конфигурации")
    parser.add_argument("--variable", action="append", default=[], metavar="KEY=VALUE",
                        help="дополнительная переменная MR-контекста, можно несколько раз")
    args = parser.parse_args()

    try:
        import yaml
    except ImportError:
        print("Нужен PyYAML: pip install pyyaml", file=sys.stderr)
        return 2

    preview = run(["gitlab-ci-local", "--file", args.file, "--preview"])
    if preview.returncode != 0 or not preview.stdout.strip():
        print("gitlab-ci-local --preview завершился с ошибкой:\n" + preview.stderr[-2000:], file=sys.stderr)
        return 2
    config = yaml.safe_load(preview.stdout)
    depends_on_changes = make_worst_case(config)

    with open(PROBE_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True)
    try:
        mr_variables = [
            "CI_PIPELINE_SOURCE=merge_request_event",
            "CI_MERGE_REQUEST_ID=1",
            "CI_MERGE_REQUEST_IID=1",
            "CI_COMMIT_BRANCH=",
        ] + args.variable
        cmd = ["gitlab-ci-local", "--file", PROBE_FILE, "--list-json",
               "--evaluate-rule-changes=false",
               "--ignore-predefined-vars", "CI_PIPELINE_SOURCE,CI_COMMIT_BRANCH"]
        for variable in mr_variables:
            cmd += ["--variable", variable]
        listing = run(cmd)
    finally:
        os.remove(PROBE_FILE)

    start = listing.stdout.find("[")
    if listing.returncode != 0 or start < 0:
        print("gitlab-ci-local --list-json завершился с ошибкой:\n" + listing.stderr[-2000:], file=sys.stderr)
        return 2
    jobs = json.loads(listing.stdout[start:])
    included = [j for j in jobs if j.get("when") != "never"]
    runnable = [j for j in included if j.get("stage") not in EDGE_STAGES]

    if runnable:
        print("OK: при любых изменениях в MR-пайплайн попадут джобы:")
        for job in runnable:
            print(f"  - {job['name']} (stage: {job['stage']})")
        return 0

    print("ПРОБЛЕМА: если изменения в MR не затронут пути из rules:changes, пайплайн не создастся,")
    print("и при «Pipelines must succeed» MR нельзя будет смёржить.")
    if depends_on_changes:
        print("Джобы, которые зависят от changes: " + ", ".join(depends_on_changes))
    edge = [j["name"] for j in included if j.get("stage") in EDGE_STAGES]
    if edge:
        print("Остаются только джобы стадий .pre/.post, а такой пайплайн не запускается: " + ", ".join(edge))
    print("Добавь джобу, которая попадает в MR-пайплайн без условия changes и стоит не в .pre/.post.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
