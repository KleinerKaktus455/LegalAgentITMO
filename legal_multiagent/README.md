# Мультиагентная система юриста

LangGraph-оркестратор разбирает карточку уголовного дела из `docs.json`, ищет аналоги в практике СОЮ и помогает собрать позицию. Это не классификатор исхода и не юридическая консультация.

## Что делает

| Агент | Роль |
|--------|------|
| Orchestrator | выбирает плейбук: досье / аналоги / риск / апелляция / черновик |
| Case Parser | нормализует карточку в Case Graph |
| Timeline | лента движения дела |
| Act Reader | фабула и резолютивка из HTML акта |
| Qualification | сверяет статьи карточки и акта |
| Analog Retriever | похожие дела по статье, региону, судье, фабуле |
| Risk | распределение исходов по аналогам |
| Appeal Strategist | типичная судьба акта в апелляции |
| Drafting | черновик позиции со ссылками на дела |
| Guard | проверяет, что цитаты и id есть в индексе |

Без `OLLAMA_API_KEY` система работает на правилах и статистике. Ключ нужен только чтобы сгладить формулировки и глубже разобрать текст акта.

## Быстрый старт

Из корня репозитория, в уже существующем `.venv`:

```bash
source .venv/bin/activate
pip install -r legal_multiagent/requirements.txt

# индекс: parquet-сплиты (text_1/2/3) + при необходимости карточки docs.json
python -m legal_multiagent ingest --source parquet --limit 3000 --reset
python -m legal_multiagent ingest --source both --limit 4000 --reset

python -m legal_multiagent status
python -m legal_multiagent ask "найди похожие дела о взыскании налоговой недоимки"
python -m legal_multiagent ask "разбери дело" --case-id 0004a19c57c5e1b8ab09047870276c76 --playbook dossier
```

## Streamlit UI

Запуск веб-интерфейса:

```bash
streamlit run legal_multiagent/ui.py
```

В интерфейсе доступны:

- **Боковая панель** — статус индекса (количество дел, пути к `docs.json`, parquet и SQLite) и форма загрузки данных с выбором источника, лимита и возможностью пересоздать SQLite.
- **Главная область** — поле запроса, выбор плейбука (`dossier`, `analogs`, `risk`, `appeal`, `draft`, `full` или авто), опциональные `case_id` / `case_number` и кнопка запуска агента.
- **Результат** — итоговый ответ в Markdown, раскрывающиеся блоки со списком шагов, таблицей аналогов, сырым JSON, а также история запросов текущей сессии.

> UI реализован в `legal_multiagent/ui.py` и переиспользует те же функции, что и CLI: `ingest`, `CaseStore` и `run_agent`.

Ключ Ollama Cloud можно держать в корневом `.env`:

```
OLLAMA_API_KEY=...
OLLAMA_BASE_URL=https://ollama.com/v1
OLLAMA_MODEL=gpt-oss:20b
```

## Плейбуки

- `dossier` — только разбор карточки
- `analogs` — подбор практики
- `risk` — оценка по аналогам
- `appeal` — апелляционная стратегия + черновик
- `draft` — черновик позиции
- `full` — вся цепочка

## Данные

- `docs.json/` — JSONL-карточки уголовных дел СОЮ (метаданные, движение, HTML акта).
- `data/correct_df_splitted_text.parquet/` — распакованный корпус сплитов: `text_1` шапка, `text_2` фабула, `text_3` резолютивка. В основном гражданские и административные акты.
- Агенты читают индекс `legal_multiagent/data/case_store.sqlite`, не сырые гигабайты.

Распаковка архива:

```bash
unrar x -y correct_df_splitted_text.parquet.rar "correct_df_splitted_text.parquet/part-*" data/
```
