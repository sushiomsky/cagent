from cagent.cli import build_config_from_args, build_parser


def test_run_cli_transport_options_reach_config(tmp_path):
    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "--workspace",
            str(tmp_path),
            "--request-retries",
            "4",
            "--retry-backoff-seconds",
            "0.25",
            "--goal",
            "demo",
        ]
    )

    config = build_config_from_args(args, workspace=args.workspace)

    assert config.request_retries == 4
    assert config.retry_backoff_seconds == 0.25


def test_loop_cli_transport_options_parse(tmp_path):
    parser = build_parser()
    args = parser.parse_args(
        [
            "loop",
            "--workspace",
            str(tmp_path),
            "--request-retries",
            "2",
            "--retry-backoff-seconds",
            "0.1",
        ]
    )

    config = build_config_from_args(args, workspace=args.workspace)

    assert config.request_retries == 2
    assert config.retry_backoff_seconds == 0.1
