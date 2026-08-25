# Отчёт о тестировании LLM-веток

## Дата
2026-08-26

## Цель
Проверить, что агенты `act_reader`, `risk`, `appeal`, `drafting` действительно используют LLM, когда доступен `OLLAMA_API_KEY`, и что финальный ответ формируется корректно.

## Окружение
- Python 3.11.5
- pytest 9.0.3
- `OLLAMA_API_KEY`: загружен из `.env` (`config.ollama_api_key()` возвращает `True`)
- Установлены зависимости из `legal_multiagent/requirements.txt` (langgraph, langchain-openai, streamlit)
- Обновлены `aiohttp` / `httpx` / `openai` для совместимости

## Проблемы окружения, решённые перед тестами
1. `langgraph` изначально не был установлен.
2. `langchain-openai` не импортировался из-за несовместимости `aiohttp` и `openai` — исправлено обновлением `aiohttp`, `httpx`, `openai`.

## Исправление в коде
В `legal_multiagent/agents/orchestrator.py` изменена логика: если пользователь **явно передал** `playbook`, orchestrator больше не вызывает LLM для его переопределения. Раньше LLM-маршрутизатор мог игнорировать выбор пользователя и выбирать `full` при наличии `case_id`.

## Файлы тестов
- `legal_multiagent/tests/test_llm_branches.py` — 4 теста LLM-веток.
- `legal_multiagent/tests/test_agent_quality_e2e.py` — e2e тест полного графа.

## Результаты прогона LLM-веток

```text
legal_multiagent/tests/test_llm_branches.py::test_act_reader_uses_llm_for_act_text  PASSED
legal_multiagent/tests/test_llm_branches.py::test_risk_adds_llm_commentary        PASSED
legal_multiagent/tests/test_llm_branches.py::test_drafting_uses_llm_when_available PASSED
legal_multiagent/tests/test_llm_branches.py::test_appeal_adds_llm_commentary        PASSED

4 passed in 29.18s
```

## Проверки

| Агент | Что проверяли | Результат |
|---|---|---|
| `act_reader` | При наличии текста акта вызывается LLM, `llm_used=True`, извлекается квалификация | ✅ |
| `risk` | Добавляет комментарий модели к статистике, `llm_used=True` | ✅ |
| `drafting` | Генерирует черновик позиции через LLM, тело документа непустое и длинное | ✅ |
| `appeal` | Добавляет комментарий модели по апелляционной практике | ✅ |

## E2E тест графа

```text
legal_multiagent/tests/test_agent_quality_e2e.py::test_full_graph_dossier_playbook  PASSED

1 passed in 0.22s
```

Граф прошёл узлы:
- `orchestrator:dossier`
- `parser`
- `timeline`
- `act_reader:splits`
- `qualification`
- `retriever:skip` (для плейбука `dossier` retriever может быть пропущен, т.к. `dossier` план не всегда включает `retriever` — см. PLAYBOOKS)

Фактически для `dossier` плана `retriever` нет, поэтому `retriever:skip` — корректное поведение.

## Полный прогон всех тестов

```text
collected 35 items
legal_multiagent/tests/test_agent_quality.py        15 passed
legal_multiagent/tests/test_agent_quality_e2e.py     1 passed
legal_multiagent/tests/test_llm_branches.py            4 passed
legal_multiagent/tests/test_normalize.py               3 passed
legal_multiagent/tests/test_system.py               12 passed

======================= 35 passed in 57.57s =======================
```

## Выводы
- LLM-ветки работают: все 4 агента используют LLM и получают ненулевой результат.
- E2E граф завершается без ошибок.
- Явно выбранный пользователем плейбук теперь не переопределяется LLM.
- Система готова к дальнейшему ручному/интеграционному тестированию через CLI или Streamlit.

## Рекомендации
1. Зарегистрировать кастомные pytest-марки `slow` в `pyproject.toml` или `pytest.ini`, чтобы убрать warning.
2. Добавить `pytest.ini` с настройками:
   ```ini
   [pytest]
   markers =
       slow: tests that call LLM or run full graph
   ```
3. Для CI/CD slow-тесты запускать отдельно: `pytest -m slow`.
4. Рассмотреть моки для LLM, чтобы не зависеть от API-ключа и сети в unit-тестах.
