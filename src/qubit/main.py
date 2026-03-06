import asyncio
from src.qubit.core.bootstrap import create_app
from src.qubit.core.runtime import run_app

async def main():
    app = await create_app()
    await run_app(app)

if __name__ == "__main__":
    asyncio.run(main())