"""Application entry point for initializing and running the async app."""

import asyncio
from src.qubit.core.bootstrap import create_app
from src.qubit.core.runtime import run_app

async def main():
    """
    Create and run the application.

    This coroutine initializes the application using the bootstrap
    process and then starts the runtime loop.

    Returns:
        None
    """
    app = await create_app()
    await run_app(app)

if __name__ == "__main__":
    asyncio.run(main())