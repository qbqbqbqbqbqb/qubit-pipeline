"""
<summary>
Application entry point. Initializes and runs the async application.
</summary>
"""

import asyncio
from src.qubit.core.bootstrap import create_app
from src.qubit.core.runtime import run_app

async def main():
    """
    <summary>
    Create and run the application.
    </summary>
    <returns>None</returns>
    """
    app = await create_app()
    await run_app(app)

if __name__ == "__main__":
    asyncio.run(main())
