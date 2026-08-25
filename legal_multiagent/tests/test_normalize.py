from legal_multiagent.etl.fields import parse_article
from legal_multiagent.etl.normalize import record_to_case
from legal_multiagent.etl.parquet_normalize import parquet_row_to_case


def test_parse_card_article():
    parsed = parse_article("Статья 158 Часть 2 п. в")
    assert parsed["article"] == "158"
    assert parsed["part"] == "2"
    assert parsed["canonical"].startswith("158")


def test_record_to_case_minimal():
    record = {
        "id": "abc",
        "fields": [
            {"name": "case_id", "value": "7105026611", "comment": "id"},
            {"name": "case_common_doc_number", "value": "1-31/2013", "comment": "номер"},
            {"name": "u_case_user_article", "value": "Статья 162 Часть 3", "comment": "статья"},
            {"name": "case_common_doc_result", "value": "Вынесен ПРИГОВОР", "comment": "результат"},
            {"name": "case_doc_instance", "value": "Первая инстанция", "comment": "инстанция"},
            {
                "name": "case_common_event_m2",
                "comment": "движение",
                "tableCols": ["28.02.2013", "17:29", "[У] Регистрация поступившего в суд дела", ""],
                "value": "28.02.2013",
            },
        ],
    }
    case = record_to_case(record)
    assert case.case_id == "7105026611"
    assert case.case_number == "1-31/2013"
    assert case.charges[0].article == "162"
    assert case.events[0].name.startswith("[У] Регистрация")


def test_parquet_row_to_case():
    case = parquet_row_to_case(
        {
            "id": "0004a19c57c5e1b8ab09047870276c76",
            "text_1": "дело № 2-416/11 заочное решение 29 июня 2011 года город ипатово ипатовский районный суд ставропольского края в составе председательствующего судьи ковалевой е.п., рассмотрев гражданское дело",
            "text_2": "инспекция обратилась в суд с иском о взыскании недоимки по налогу",
            "text_3": "в удовлетворении исковых требований отказать в связи с истечением срока",
        }
    )
    assert case.case_id == "0004a19c57c5e1b8ab09047870276c76"
    assert case.case_number.startswith("2-416")
    assert case.source == "parquet"
    assert "Гражданское" in case.kind
    assert case.split_fabula.startswith("инспекция")
    assert case.document_result == "В иске отказано"
