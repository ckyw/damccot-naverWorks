from src.tree_exports import folder_tree_markdown, write_tree_exports


def test_tree_exports_create_csv_and_markdown(tmp_path):
    items = [
        {
            "fileName": "HACCP",
            "filePath": "/품질관리/HACCP/",
            "fileType": "FOLDER",
            "isFolder": True,
            "depth": 1,
        },
        {
            "fileName": "=formula.xlsx",
            "filePath": "/품질관리/HACCP/=formula.xlsx",
            "fileType": "DOC",
            "isFolder": False,
            "depth": 2,
        },
    ]

    write_tree_exports(items, tmp_path)

    csv_text = (tmp_path / "reports" / "sharedrive_tree.csv").read_text(encoding="utf-8-sig")
    markdown = (tmp_path / "reports" / "folder_tree.md").read_text(encoding="utf-8")
    assert "'=formula.xlsx" in csv_text
    assert "- [folder] HACCP" in markdown
    assert "  - [file] =formula.xlsx" in markdown
    assert folder_tree_markdown([]) == "# Shared Drive Folder Tree\n\n"
