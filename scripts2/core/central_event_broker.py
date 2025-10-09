import asyncio
import threading

class CentralEventBroker:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.queue = None
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        self._queue_created_event = threading.Event()
        self.loop.call_soon_threadsafe(self._create_queue)

        self._queue_created_event.wait()

    def _create_queue(self):
        self.queue = asyncio.Queue()
        self._queue_created_event.set()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join()

    def publish_event(self, event):
        def _put():
            try:
                self.queue.put_nowait(event)
                # print(f"Event published: {event}")
            except asyncio.QueueFull:
                print(f"Warning: Event queue full, dropped event: {event}") #will never happen yet
            except Exception as e:
                print(f"Error publishing event: {e}")

        self.loop.call_soon_threadsafe(_put)

    async def subscribe(self):
        while True:
            event = await self.queue.get()
            yield event
