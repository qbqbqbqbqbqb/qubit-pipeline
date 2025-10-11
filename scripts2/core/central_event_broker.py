"""
Central event broker module for asynchronous event handling.

This module provides the CentralEventBroker class, which manages an asynchronous event queue
running in a separate thread, allowing publish-subscribe pattern for event-driven communication.
"""

import asyncio
import threading

class CentralEventBroker:
    """
    Central event broker for managing asynchronous events.

    Runs an asyncio event loop in a separate thread and provides methods to publish events
    and subscribe to them asynchronously.
    """
    def __init__(self):
        """
        Initializes the CentralEventBroker with a new event loop in a separate thread.
        """
        self.loop = asyncio.new_event_loop()
        self.queue = None
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        self._queue_created_event = threading.Event()
        self.loop.call_soon_threadsafe(self._create_queue)

        self._queue_created_event.wait()

    def _create_queue(self):
        """
        Creates the asyncio queue and sets the creation event.
        """
        self.queue = asyncio.Queue()
        self._queue_created_event.set()

    def _run_loop(self):
        """
        Runs the asyncio event loop.
        """
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop(self):
        """
        Stops the event loop and joins the thread.
        """
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join()

    def publish_event(self, event):
        """
        Publishes an event to the queue from a thread-safe context.

        Args:
            event: The event data to publish.
        """
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
        """
        Asynchronously subscribes to events from the queue.

        Yields:
            event: The next event from the queue.
        """
        while True:
            event = await self.queue.get()
            yield event
