from src.batcher import build_batches


def test_build_batches_omits_sensitive_ids():
    items = [
        {
            "fileId": "secret-id",
            "fileName": "상세페이지.jpg",
            "filePath": "/제품/상세페이지.jpg",
            "fileType": "file",
            "extension": "jpg",
            "modifiedTime": "2026-07-12T00:00:00+09:00",
            "depth": 2,
        }
    ]

    batches = build_batches(items)
    product_item = batches["batch_002_product_assets.json"][0]

    assert product_item["fileName"] == "상세페이지.jpg"
    assert "fileId" not in product_item


def test_top_level_batch_uses_depth_one_items():
    items = [
        {"fileName": "A", "filePath": "/A", "fileType": "folder", "depth": 1},
        {"fileName": "B", "filePath": "/A/B", "fileType": "file", "depth": 2},
    ]

    batches = build_batches(items)

    assert len(batches["batch_001_top_level.json"]) == 1

