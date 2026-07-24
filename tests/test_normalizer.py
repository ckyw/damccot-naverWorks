from src.normalizer import normalize_item


def test_normalize_file_item_extracts_extension():
    item = {
        "fileId": "file-1",
        "parentFileId": "folder-1",
        "fileName": "IMG_0001.JPG",
        "filePath": "/제품/IMG_0001.JPG",
        "fileType": "file",
        "fileSize": 123,
    }

    normalized = normalize_item(item, depth=2, collected_at="2026-07-12T00:00:00+09:00")

    assert normalized["extension"] == "jpg"
    assert normalized["isFolder"] is False
    assert normalized["depth"] == 2


def test_normalize_folder_item_has_no_extension():
    item = {"fileId": "folder-1", "fileName": "제품", "fileType": "folder"}

    normalized = normalize_item(item, depth=1, collected_at="2026-07-12T00:00:00+09:00")

    assert normalized["extension"] is None
    assert normalized["isFolder"] is True

