import tempfile
import unittest
from parcelseal.publisher import LegacySender
from parcelseal.transport import FileTransport


class ExistingSender(unittest.TestCase):
    def test_legacy_sender_and_provider_dedup(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = FileTransport(directory)
            sender = LegacySender(transport)
            self.assertEqual(sender.send("a", b"payload"), sender.send("a", b"payload"))
            self.assertEqual(transport.effect_count(), 1)
