"""Start World Freight Idle with ``python main.py``."""

import os

import uvicorn


def main() -> None:
    """Run the browser game with one shared provider rate limiter."""
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
