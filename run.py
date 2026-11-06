"""Entry point for running SpendSentinel with Uvicorn."""

import uvicorn
from app.config import settings


def main() -> None:
    """Start the Uvicorn server on port 8000."""
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=8000,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    main()
