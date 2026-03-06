class App:

    def __init__(self):
        self.services = []
        self.state = None
        self.event_bus = None
        self.server = None

    def add_service(self, service):
        self.services.append(service)