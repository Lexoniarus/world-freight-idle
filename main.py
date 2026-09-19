"""Start World Freight Idle with ``python main.py``."""

import os

import uvicorn


def main() -> None:
    """Run the server-authoritative browser game in one process."""
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
