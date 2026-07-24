import json

from src.merge_parts import merge_part_items


def test_merge_part_items_deduplicates_file_ids(tmp_path):
    for name, items in {
        "root": [{"fileId": "folder-1", "fileName": "HACCP", "filePath": "/HACCP/"}],
        "child": [
            {"fileId": "folder-1", "fileName": "HACCP", "filePath": "/HACCP/"},
            {"fileId": "file-1", "fileName": "check.xlsx", "filePath": "/HACCP/check.xlsx"},
        ],
    }.items():
        raw_dir = tmp_path / name / "raw"
        raw_dir.mkdir(parents=True)
        (raw_dir / "sharedrive_tree_raw.json").write_text(
            json.dumps({"items": items}), encoding="utf-8"
        )

    merged = merge_part_items(tmp_path)

    assert [item["fileId"] for item in merged] == ["folder-1", "file-1"]
