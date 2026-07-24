from src.config import build_parser


def test_full_depth_flag_overrides_environment_depth():
    args = build_parser().parse_args(["--full-depth"])

    assert args.full_depth is True
    assert args.max_depth is None


def test_secret_manager_arguments_are_parsed():
    args = build_parser().parse_args(
        [
            "--gcp-project",
            "naver-sharedrive",
            "--client-secret-name",
            "client-secret",
            "--refresh-token-name",
            "refresh-token",
        ]
    )

    assert args.gcp_project == "naver-sharedrive"
    assert args.client_secret_name == "client-secret"
    assert args.refresh_token_name == "refresh-token"
