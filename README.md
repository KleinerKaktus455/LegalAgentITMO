# Научка: юрист

Мультиагентная система юриста по судебным актам.

- Актуальный код: [`legal_multiagent/`](legal_multiagent/README.md)
- Старые ноутбуки и бейзлайн: [`old_project/`](old_project/README.md)
- Карточки СОЮ: `docs.json/` (JSONL, не открывать целиком)
- Сплиты актов: `data/correct_df_splitted_text.parquet/` (`text_1` / `text_2` / `text_3`)

## Быстрый старт через веб-интерфейс

```bash
# Из корня репозитория, где лежит папка legal_multiagent/
source .venv/bin/activate
pip install -r legal_multiagent/requirements.txt
streamlit run legal_multiagent/ui.py
```

Интерфейс позволяет загрузить индекс через боковую панель и задавать вопросы агенту в диалоговом режиме. См. подробнее в [`legal_multiagent/README.md`](legal_multiagent/README.md).
