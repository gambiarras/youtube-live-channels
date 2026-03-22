from live_stream_catalog.cli import parse_args
from live_stream_catalog.config import AppConfig
from live_stream_catalog.logging_config import configure_logging
from live_stream_catalog.services.build import run_build
from live_stream_catalog.services.refresh import run_refresh


def main() -> None:
    args = parse_args()
    config = AppConfig.from_args(args)

    configure_logging(config.log_level)

    if args.command == "build":
        run_build(config)
        return

    if args.command == "refresh":
        run_refresh(config)
        return

    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()