import os

import uvicorn


if __name__ == "__main__":
    # Keep one launcher for local and container development. Reload is opt-in
    # so a production process does not run a file watcher by accident.
    uvicorn.run(
        "app:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() in {"1", "true", "yes", "on"},
    )
