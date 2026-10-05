"""Loopback API entry point used by the packaged Stockwise desktop app."""

import argparse
import uvicorn
from app.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Stockwise AI local API service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    if args.host != "127.0.0.1":
        parser.error("The desktop API service must bind to 127.0.0.1")
    configuration = uvicorn.Config(app, host=args.host, port=args.port, log_level="info")
    server = uvicorn.Server(configuration)
    app.state.desktop_server = server
    server.run()


if __name__ == "__main__":
    main()
