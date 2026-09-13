# legal_multiagent

Разбирает карточку судебного дела, ищет аналоги в практике [СОЮ](https://ru.wikipedia.org/wiki/Суд_общей_юрисдикции) и собирает черновик позиции. Это не классификатор исхода и не юридическая консультация.

Система читает индекс SQLite, а не сырые гигабайты JSONL/parquet. Без `OLLAMA_API_KEY` агенты работают на правилах и статистике по индексу; ключ нужен только чтобы сгладить формулировки и глубже разобрать текст акта.

## Background

Корпус — карточки дел и тексты судебных актов. У записи нет готовой метки «исход», а тексты смешанные: гражданские, административные, редко уголовные. Поэтому задача — не предсказать приговор, а нормализовать дело в [Case Graph](#case-graph) и подобрать похожую практику.

[LangGraph](https://langchain-ai.github.io/langgraph/) держит линейную цепочку агентов. [Orchestrator](#playbooks) выбирает playbook и пишет `plan`; узлы вне плана делают `skip`.

Старые ноутбуки и бейзлайн лежат в [`old_project/`](old_project/). Актуальный код — пакет [`legal_multiagent/`](legal_multiagent/).

## Usage

Из корня репозитория, в `.venv`:

```bash
source .venv/bin/activate
pip install -r legal_multiagent/requirements.txt

python -m legal_multiagent ingest --source parquet --limit 3000
python -m legal_multiagent status
python -m legal_multiagent ask "найди похожие дела о взыскании налоговой недоимки"
```

Ожидаемый вывод `status` (числа зависят от индекса):

```text
docs.json: .../docs.json
parquet: .../data/correct_df_splitted_text.parquet
store: .../legal_multiagent/data/case_store.sqlite
дел в индексе: 3000
```

Ожидаемый вид ответа `ask` (плейбук `analogs` или `risk`):

```text
Плейбук: analogs

## Аналоги
| № дела | Статья | Исход | Score | Причины |
| --- | --- | --- | --- | --- |
| 2-123/2018 | — | Взыскание | 0.412 | фабула |
```

Разбор конкретной карточки:

```bash
python -m legal_multiagent ask "разбери дело" \
  --case-id 0004a19c57c5e1b8ab09047870276c76 \
  --playbook dossier \
  --verbose
```

Веб-интерфейс (тот же `ingest` / `run_agent`):

```bash
streamlit run legal_multiagent/ui.py
```

Программный вызов:

```python
from legal_multiagent.graph import run_agent

result = run_agent(
    "найди похожие дела о взыскании налоговой недоимки",
    playbook="analogs",
)
print(result["final_answer"])
print(result["playbook"], result["steps_done"])
```

## API

### CLI

```text
python -m legal_multiagent <command>
```

| Команда | Назначение |
|---------|------------|
| `ingest` | загрузить parquet и/или `docs.json` в SQLite |
| `status` | пути к данным и число дел в индексе |
| `ask QUERY` | прогнать граф и напечатать `final_answer` |

`ingest`:

| Аргумент | Тип | По умолчанию | Смысл |
|----------|-----|--------------|--------|
| `--limit` | `int` | `2000` | сколько карточек записать; `0` — все |
| `--source` | `parquet` \| `docs` \| `both` | `both` | откуда читать |
| `--docs-dir` | path | `docs.json/` | JSONL-карточки СОЮ |
| `--parquet-dir` | path | `data/correct_df_splitted_text.parquet/` | сплиты `text_1` / `text_2` / `text_3` |
| `--reset` | flag | off | удалить SQLite и создать заново |

`ask`:

| Аргумент | Тип | По умолчанию | Смысл |
|----------|-----|--------------|--------|
| `query` | `str` | обязателен | вопрос юриста |
| `--case-id` | `str` | `None` | id карточки в индексе |
| `--case-number` | `str` | `None` | номер дела, поиск по `LIKE` |
| `--playbook` | см. ниже | авто | иначе Orchestrator выбирает сам |
| `--json` | flag | off | сырое состояние, не только ответ |
| `--verbose` | flag | off | цепочка `steps_done` |

Код выхода `ask`: `2`, если индекс пуст.

### `run_agent`

```python
run_agent(
    query: str,
    case_id: str | None = None,
    case_number: str | None = None,
    playbook: str | None = None,
) -> dict
```

Возвращает [AgentState](legal_multiagent/state.py). Полезные ключи:

| Ключ | Тип | Смысл |
|------|-----|--------|
| `playbook` | `str` | выбранный сценарий |
| `plan` | `list[str]` | какие узлы реально исполнять |
| `case` | `dict` | Case Graph исходного дела |
| `analogs` | `list[dict]` | похожие дела (`case_id`, `score`, `reasons`, …) |
| `risk` / `appeal` / `draft` / `guard` | `dict` | выходы профильных агентов |
| `final_answer` | `str` | markdown для юриста |
| `steps_done` | `list[str]` | факт прогона, включая `*:skip` |
| `gaps` / `errors` | `list[str]` | пробелы данных и сбои |

### Playbooks

Граф всегда линейный: `START → orchestrator → parser → timeline → act_reader → qualification → retriever → risk → appeal → draft → guard → respond → END`. Исполняются только имена из `plan`.

| Playbook | Что в `plan` |
|----------|----------------|
| `dossier` | parser, timeline, act_reader, qualification, respond |
| `analogs` | parser, qualification, retriever, respond |
| `risk` | parser … retriever, risk, guard, respond |
| `appeal` | parser … retriever, appeal, draft, guard, respond |
| `draft` | parser, act_reader, qualification, retriever, draft, guard, respond |
| `full` | вся цепочка |

Автовыбор (если `--playbook` не задан): правила по тексту запроса, при наличии ключа — правка через Ollama.

### `ingest`

```python
ingest(
    limit: int | None = None,          # None → INGEST_LIMIT или 2000
    docs_dir: Path | None = None,
    parquet_root: Path | None = None,
    reset: bool = False,
    source: str = "both",              # parquet | docs | both
    progress: Callable | None = None,
) -> dict  # written, skipped, docs_shards, parquet_parts, source
```

Уже лежащие в индексе parquet-id не переписываются. `source=parquet` после `docs.json` дописывает сплиты `text_1/2/3` в существующую карточку.

### Case Graph

Нормализованная карточка: id, номер, суд, судья, регион, статьи, лента движения, фабула, резолютивка. Строится из JSONL (`etl/normalize.py`) или строки parquet (`etl/parquet_normalize.py`).

### Переменные окружения

Корень репозитория или `legal_multiagent/.env`:

| Переменная | По умолчанию | Смысл |
|------------|--------------|--------|
| `DOCS_JSON_DIR` | `docs.json/` | карточки СОЮ |
| `PARQUET_DIR` | `data/correct_df_splitted_text.parquet/` | сплиты актов |
| `CASE_STORE_PATH` | `legal_multiagent/data/case_store.sqlite` | индекс |
| `INGEST_LIMIT` | `2000` | лимит, если `ingest(limit=None)` |
| `OLLAMA_API_KEY` | пусто | нет ключа — без LLM |
| `OLLAMA_BASE_URL` | `https://ollama.com/v1` | OpenAI-совместимый endpoint |
| `OLLAMA_MODEL` | `gpt-oss:20b` | модель |

## Install

Нужны Python 3.11+ и уже существующий `.venv` в корне:

```bash
git clone <repo>
cd научка_юрист
source .venv/bin/activate
pip install -r legal_multiagent/requirements.txt
```

Зависимости: `langgraph`, `langchain-core`, `langchain-openai`, `pydantic`, `python-dotenv`, `pyarrow`, `streamlit`.

Индекс в git не входит. Положите распакованный parquet в `data/correct_df_splitted_text.parquet/` (и при необходимости JSONL в `docs.json/`), затем `ingest`. Распаковка архива сплитов:

```bash
unrar x -y correct_df_splitted_text.parquet.rar "correct_df_splitted_text.parquet/part-*" data/
```

Полный корпус (~1,86 млн строк) даёт SQLite порядка десятков гигабайт. Для проверки достаточно `--limit 3000`.

Проверка:

```bash
python -m pytest legal_multiagent/tests -q
```

## License

Лицензия не указана: учебный репозиторий практики. Код можно читать и запускать локально; публичное распространение без явной лицензии не предполагается.
