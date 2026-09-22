from backend import rules


def test_receipt_table_reconstruction_keeps_rows_and_rejects_dates():
    blocks = [{"rows": [
        ["항목", "항목", "항목", "급여", "급여", "비급여", "비급여"],
        ["항목", "항목", "항목", "일부 본인부담", "공단부담금", "선택 진료료", "선택진료료 이외"],
        ["항목", "항목", "항목", "본인부담금", "공단부담금", "선택 진료료", "선택진료료 이외"],
        ["기본항목", "투약 및 조제료", "행위료", "1,200", "2,300", "", ""],
        ["기본항목", "식대", "식대", "", "", "", ""],
        ["안내", "2024년 1월 1일", "2024년 1월 1일", "", "", "", ""],
    ]}]

    out = rules.apply("진료비영수증", {"항목내역": [{"항목": "진찰료"}]}, blocks)
    rows = {row["항목"]: row for row in out["항목내역"]}

    assert set(rows) == {"진찰료", "투약및조제료_행위료", "식대"}
    assert rows["투약및조제료_행위료"]["본인부담금"] == "1200"
    assert rows["투약및조제료_행위료"]["공단부담금"] == "2300"


def test_receipt_reconstruction_supports_one_header_and_item_column():
    blocks = [{"rows": [
        ["항목", "본인부담금", "공단부담금"],
        ["진찰료", "0", "200"],
        ["합계", "0", "200"],
    ]}]

    rows = rules.apply("진료비영수증", {"항목내역": [{"항목": "합계"}]}, blocks)["항목내역"]

    assert [row["항목"] for row in rows] == ["진찰료", "합계"]
    assert rows[0]["공단부담금"] == "200"


def test_receipt_reconstruction_does_not_overwrite_a_duplicate_leaf_header():
    blocks = [{"rows": [
        ["항목", "본인부담금", "본인부담금", "공단부담금"],
        ["항목", "본인부담금", "본인부담금", "공단부담금"],
        ["항목", "본인부담금", "본인부담금", "공단부담금"],
        ["진찰료", "100", "999", "200"],
    ]}]

    row = rules.apply("진료비영수증", {}, blocks)["항목내역"][0]

    assert row["본인부담금"] is None
    assert row["공단부담금"] == "200"


def test_receipt_reconstruction_reads_all_header_rows_before_the_first_item():
    blocks = [{"rows": [
        ["항목", "급여", "급여"],
        ["항목", "일부 본인부담", "공단부담금"],
        ["항목", "본인부담금", "공단부담금"],
        ["항목", "본인부담금", "공단부담금"],
        ["식대", "100", "200"],
    ]}]

    row = rules.apply("진료비영수증", {}, blocks)["항목내역"][0]

    assert row["항목"] == "식대"
    assert row["본인부담금"] == "100"
    assert row["공단부담금"] == "200"
