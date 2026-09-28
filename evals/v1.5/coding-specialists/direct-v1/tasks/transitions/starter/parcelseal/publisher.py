"""Legacy send remains supported; the durable Publisher is the requested feature."""


class PublishConflict(ValueError):
    pass


class LegacySender:
    def __init__(self, transport):
        self.transport = transport

    def send(self, name, payload):
        return self.transport.send("legacy", name, payload)


class Publisher:
    def __init__(self, state_path, transport):
        self.state_path = state_path
        self.transport = transport

    def publish(self, tenant, key, payload):
        raise NotImplementedError("durable replay and uncertain-outcome recovery")

    def close(self):
        pass
