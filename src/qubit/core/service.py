class Service:

    SUBSCRIPTIONS = {}

    def __init__(self, name):
        self.name = name
        self.event_bus = None

    async def start(self, app):
        self.event_bus = app.event_bus
        self._register_subscriptions()


    async def stop(self):
        pass

    def _register_subscriptions(self):
        for event_type, handler_name in self.SUBSCRIPTIONS.items():
            handler = getattr(self, handler_name)
            self.event_bus.subscribe(event_type, handler)