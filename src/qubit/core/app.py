"""Top-level application container holding services, state, and the event bus."""

class App:
    """Root application object that owns all services and shared state."""

    def __init__(self):
        """Initialise empty service list and placeholder state/bus."""
        self.services = []
        self.state = None
        self.event_bus = None
        self.server = None

    def add_service(self, service):
        """Register a service to be started with the application."""
        self.services.append(service)
