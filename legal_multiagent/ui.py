from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from legal_multiagent.config import docs_json_dir, parquet_dir, store_path
from legal_multiagent.etl.ingest import ingest
from legal_multiagent.store.sqlite_store import CaseStore


def _store() -> CaseStore:
    return CaseStore()


def _render_sidebar() -> None:
    st.sidebar.title("Юрист: мультиагентная система")
    st.sidebar.caption("Разбор карточек СОЮ, поиск аналогов, оценка рисков, черновики позиций.")

    with st.sidebar.container(border=True):
        st.subheader("Состояние индекса")
        store = _store()
        st.write(f"**Дел в индексе:** {store.count()}")
        st.write(f"`docs.json`: `{docs_json_dir()}`")
        st.write(f"`parquet`: `{parquet_dir()}`")
        st.write(f"`store`: `{store_path()}`")

    st.sidebar.divider()
    st.sidebar.subheader("Загрузка данных")

    source = st.sidebar.selectbox(
        "Источник",
        options=["both", "parquet", "docs"],
        format_func=lambda x: {
            "both": "parquet + docs.json",
            "parquet": "только parquet-сплиты",
            "docs": "только карточки docs.json",
        }[x],
    )
    limit = st.sidebar.number_input(
        "Лимит карточек",
        min_value=0,
        max_value=100_000,
        value=2000,
        step=100,
        help="0 означает «все».",
    )
    reset = st.sidebar.checkbox("Пересоздать SQLite", value=False)

    if st.sidebar.button("🔄 Загрузить", use_container_width=True):
        with st.sidebar.status("Идёт загрузка…", expanded=True) as status:
            try:
                stats = ingest(
                    limit=int(limit) if limit else 0,
                    source=str(source),
                    reset=bool(reset),
                )
                st.sidebar.write(stats)
                status.update(label=f"Загружено {stats['written']} дел", state="complete")
                st.rerun()
            except Exception as exc:
                status.update(label="Ошибка загрузки", state="error")
                st.sidebar.error(str(exc))


def _playbook_label(pb: str) -> str:
    return {
        "auto": "Авто (по запросу)",
        "dossier": "Досье — разбор карточки",
        "analogs": "Аналоги — подбор практики",
        "risk": "Риск — оценка исходов",
        "appeal": "Апелляция — стратегия",
        "draft": "Черновик позиции",
        "full": "Полная цепочка",
    }.get(pb, pb)


def _format_analogs(analogs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for a in analogs:
        rows.append(
            {
                "№ дела": a.get("case_number") or a.get("case_id"),
                "id": a.get("case_id"),
                "Статья": a.get("article") or "—",
                "Исход": a.get("document_result") or a.get("card_result") or "—",
                "Регион": a.get("region") or "—",
                "Судья": a.get("judge") or "—",
                "Score": a.get("score"),
                "Причины": ", ".join(a.get("reasons") or []),
            }
        )
    return rows


def main() -> None:
    st.set_page_config(
        page_title="Юрист: мультиагентная система",
        page_icon="⚖️",
        layout="wide",
    )

    _render_sidebar()

    st.header("⚖️ Задайте вопрос агенту")

    if "history" not in st.session_state:
        st.session_state.history = []
    if "last_result" not in st.session_state:
        st.session_state.last_result = None

    store_count = _store().count()
    if store_count == 0:
        st.warning(
            "Индекс пуст. Загрузите данные через боковую панель "
            "(например, parquet, limit 3000), прежде чем задавать вопросы."
        )

    with st.container(border=True):
        query = st.text_area(
            "Вопрос / запрос",
            placeholder="Например: найди похожие дела о взыскании налоговой недоимки",
            height=120,
        )

        col1, col2, col3 = st.columns([2, 2, 4])
        with col1:
            playbook = st.selectbox(
                "Плейбук",
                options=["auto", "dossier", "analogs", "risk", "appeal", "draft", "full"],
                format_func=_playbook_label,
                help="auto выбирает плейбук по ключевым словам запроса.",
            )
        with col2:
            case_id = st.text_input("case_id", placeholder="0004a19c57c5e1b8ab09047870276c76")
        with col3:
            case_number = st.text_input("№ дела", placeholder="02-0001/2024")

        run_disabled = store_count == 0 or not query.strip()
        run = st.button(
            "▶️ Запустить агента",
            disabled=run_disabled,
            use_container_width=True,
        )

    if run and query.strip():
        # Lazy import: graph is heavy and needed only on run.
        from legal_multiagent.graph import run_agent

        selected_playbook = None if playbook == "auto" else playbook
        with st.spinner("Агенты работают…"):
            try:
                result = run_agent(
                    query=query.strip(),
                    case_id=case_id.strip() or None,
                    case_number=case_number.strip() or None,
                    playbook=selected_playbook,
                )
            except Exception as exc:
                st.error(f"Ошибка при выполнении: {exc}")
                result = None

        if result:
            st.session_state.last_result = result
            st.session_state.history.append(
                {
                    "query": query.strip(),
                    "playbook": result.get("playbook") or playbook,
                    "case_id": result.get("case_id") or case_id,
                }
            )

    result = st.session_state.last_result
    if result:
        st.divider()
        st.subheader("Итоговый ответ")
        st.markdown(result.get("final_answer") or "_пустой ответ_")

        with st.expander("🔍 Шаги выполнения"):
            steps = result.get("steps_done") or []
            st.write(" → ".join(steps) if steps else "—")

        with st.expander("📋 Аналоги таблицей"):
            analogs = result.get("analogs") or []
            if analogs:
                try:
                    import pandas as pd

                    st.dataframe(
                        pd.DataFrame(_format_analogs(analogs)),
                        use_container_width=True,
                        hide_index=True,
                    )
                except Exception:
                    st.json(analogs)
            else:
                st.write("Аналоги не найдены.")

        with st.expander("📦 Сырые данные (JSON)"):
            st.json(
                {
                    key: result.get(key)
                    for key in (
                        "playbook",
                        "plan",
                        "case_id",
                        "qualification",
                        "analogs",
                        "risk",
                        "appeal",
                        "guard",
                        "final_answer",
                        "steps_done",
                        "gaps",
                        "errors",
                    )
                },
                expanded=False,
            )

        gaps = result.get("gaps") or []
        errors = result.get("errors") or []
        if gaps or errors:
            with st.expander("⚠️ Пробелы и ошибки", expanded=True):
                if gaps:
                    st.write("**Пробелы:**")
                    for g in gaps:
                        st.write(f"- {g}")
                if errors:
                    st.write("**Ошибки:**")
                    for e in errors:
                        st.write(f"- {e}")

    if st.session_state.history:
        st.divider()
        st.subheader("История запросов")
        for i, item in enumerate(reversed(st.session_state.history[-10:]), start=1):
            st.write(
                f"{i}. **{item['query']}** — плейбук: `{item['playbook']}`"
                + (f", дело: `{item['case_id']}`" if item.get("case_id") else "")
            )


if __name__ == "__main__":
    main()
