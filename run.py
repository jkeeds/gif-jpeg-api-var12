"""Start the Bottle app with file or SQLite data storage."""

import argparse
import configparser
from pathlib import Path

from bottle import run

from src.api import create_app
from src.service import ConversionService
from src.storage import FileStore


ROOT = Path(__file__).resolve().parent


def load_auth(config_path):
    """Read HTTP Basic credentials from the application configuration file."""
    config = configparser.ConfigParser()
    if not config.read(config_path, encoding="utf-8"):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    return config["auth"]["username"], config["auth"]["password"]


def main(argv=None):
    """Configure and start the HTTP server."""
    parser = argparse.ArgumentParser(description="GIF to JPEG HTTP API")
    parser.add_argument("--backend", choices=("file",),
                        default="file")
    parser.add_argument("--config", type=Path, default=ROOT / "config.ini")
    parser.add_argument("--test-mode", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    username, password = load_auth(args.config)
    folder = ROOT / "data"
    store = FileStore(folder / "records.json")
    service = ConversionService(
        store, folder / "uploads", folder / "outputs", args.test_mode,
    )
    try:
        run(app=create_app(service, username, password),
            host=args.host, port=args.port, quiet=False)
    finally:
        service.close()


if __name__ == "__main__":
    main()
