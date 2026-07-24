from src import collector


class StaticTokenProvider:
    refresh_token = ""

    def get_access_token(self):
        return "test-token"

    def invalidate_access_token(self):
        pass


def test_collection_excludes_sensitive_folder_and_does_not_traverse_it(monkeypatch):
    requested_folder_ids = []

    def fake_list_children(sharedrive_id, folder_id, token_provider, cursor, **kwargs):
        requested_folder_ids.append(folder_id)
        if folder_id is None:
            return {
                "files": [
                    {"fileId": "safe-folder", "fileName": "HACCP", "fileType": "FOLDER"},
                    {"fileId": "secret-folder", "fileName": "아이디비번", "fileType": "FOLDER"},
                ]
            }
        if folder_id == "safe-folder":
            return {"files": [{"fileId": "safe-file", "fileName": "checklist.xlsx", "fileType": "DOC"}]}
        raise AssertionError("Sensitive folders must not be traversed")

    monkeypatch.setattr(collector, "list_children", fake_list_children)

    items = collector.collect_drive_tree("drive-id", None, StaticTokenProvider())

    assert requested_folder_ids == [None, "safe-folder"]
    assert [item["fileName"] for item in items] == ["HACCP", "checklist.xlsx"]
