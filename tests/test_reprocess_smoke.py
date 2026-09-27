"""Smoke 보고서가 값 없이 변경과 유일한 silver 행만 집계하는지 확인한다."""

from scripts.reprocess_smoke import changed_leaves, changed_silver_matches


def test_changed_leaves_uses_json_pointer_for_slashes_and_tildes():
    before = {"외래/입원": "01", "a~b": [{"x/y": "old"}]}
    after = {"외래/입원": "02", "a~b": [{"x/y": "new"}]}
    paths = changed_leaves(before, after)

    assert paths == ["a~0b/0/x~1y", "외래~1입원"]
    counts = changed_silver_matches("진료비영수증", before, after, ["외래~1입원"],
                                    {"fields": {"외래/입원": "02"}, "provenance": {"unknown_fields": []}})
    assert counts["known"] == 1 and counts["baseline_matches"] == 0 and counts["candidate_matches"] == 1


def test_changed_table_leaf_uses_unique_row_identity_and_excludes_unknown():
    before = {"항목내역": [{"항목": "검사료", "공단부담금": "10"},
                      {"항목": "입원료", "공단부담금": "20"}]}
    after = {"항목내역": [{"항목": "검사료", "공단부담금": "30"},
                     {"항목": "입원료", "공단부담금": "40"}]}
    label = {"fields": {"항목내역": [{"항목": "입원료", "공단부담금": "40"},
                                {"항목": "검사료", "공단부담금": "30"}]},
             "provenance": {"unknown_fields": ["항목내역.0.공단부담금"]}}

    counts = changed_silver_matches("진료비영수증", before, after, changed_leaves(before, after), label)

    assert counts == {"known": 1, "unknown_excluded": 1, "unmatched_or_unlabeled": 0,
                      "baseline_matches": 0, "candidate_matches": 1, "improved": 1, "regressed": 0}


def test_ambiguous_duplicate_rows_are_not_scored():
    before = {"항목내역": [{"항목": "검사료", "공단부담금": "10"},
                      {"항목": "검사료", "공단부담금": "20"}]}
    after = {"항목내역": [{"항목": "검사료", "공단부담금": "30"},
                     {"항목": "검사료", "공단부담금": "40"}]}
    label = {"fields": {"항목내역": [{"항목": "검사료", "공단부담금": "30"},
                                {"항목": "검사료", "공단부담금": "40"}]},
             "provenance": {"unknown_fields": []}}

    counts = changed_silver_matches("진료비영수증", before, after, changed_leaves(before, after), label)

    assert counts["known"] == 0 and counts["unmatched_or_unlabeled"] == 2


def test_reordered_candidate_rows_are_not_compared_to_the_old_identity():
    before = {"항목내역": [{"항목": "검사료", "공단부담금": "10"},
                      {"항목": "입원료", "공단부담금": "20"}]}
    after = {"항목내역": [{"항목": "입원료", "공단부담금": "20"},
                     {"항목": "검사료", "공단부담금": "10"}]}
    label = {"fields": {"항목내역": before["항목내역"]}, "provenance": {"unknown_fields": []}}

    counts = changed_silver_matches("진료비영수증", before, after, changed_leaves(before, after), label)

    assert counts["known"] == 0 and counts["unmatched_or_unlabeled"] == 4


def test_amount_null_and_zero_count_as_loose_match_only():
    before = {"항목내역": [{"항목": "검사료", "공단부담금": "5"}]}
    after = {"항목내역": [{"항목": "검사료", "공단부담금": None}]}
    label = {"fields": {"항목내역": [{"항목": "검사료", "공단부담금": "0"}]},
             "provenance": {"unknown_fields": []}}

    counts = changed_silver_matches("진료비영수증", before, after, changed_leaves(before, after), label)

    assert counts["known"] == 1 and counts["candidate_matches"] == 1 and counts["improved"] == 1
