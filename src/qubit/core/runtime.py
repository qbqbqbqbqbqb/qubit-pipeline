import asyncio
import signal


async def run_app(app):

    tasks = []

    # start services
    for service in app.services:
        task = asyncio.create_task(service.start(app))
        tasks.append(task)

    def shutdown():
        app.state.shutdown.set()

    signal.signal(signal.SIGINT, lambda s, f: shutdown())
    signal.signal(signal.SIGTERM, lambda s, f: shutdown())

    await app.state.shutdown.wait()

    for service in app.services:
        await service.stop()

    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)