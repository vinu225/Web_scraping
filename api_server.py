"""
api_server.py
==============
Standalone entry point for the News Scraper FastAPI server.

Usage
─────
    # Default: http://localhost:8000
    C:\\Users\\vinuj\\anaconda3\\python.exe api_server.py

    # Custom port
    C:\\Users\\vinuj\\anaconda3\\python.exe api_server.py --port 8080

    # Development mode with auto-reload
    C:\\Users\\vinuj\\anaconda3\\python.exe api_server.py --reload

    # Production mode
    C:\\Users\\vinuj\\anaconda3\\python.exe api_server.py --workers 4

After starting:
    Swagger UI  → http://localhost:8000/docs
    ReDoc       → http://localhost:8000/redoc
    Health      → http://localhost:8000/api/v1/health
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="api_server",
        description="News Scraper FastAPI server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=False,
        help="Enable auto-reload on code changes (development only)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of uvicorn worker processes (default: 1; use >1 for production)",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug"],
        help="Uvicorn log level (default: info)",
    )

    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("ERROR: uvicorn is not installed. Run: pip install uvicorn[standard]", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  NEWS SCRAPER API SERVER")
    print("=" * 60)
    print(f"  Listening on  : http://{args.host}:{args.port}")
    print(f"  Swagger UI    : http://localhost:{args.port}/docs")
    print(f"  Health check  : http://localhost:{args.port}/api/v1/health")
    print(f"  Workers       : {args.workers}")
    print(f"  Auto-reload   : {args.reload}")
    print("=" * 60 + "\n")

    uvicorn.run(
        "api.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
