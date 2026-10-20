import socket
import threading
import unittest

import protocol
from client import ServerError, TaskClient
from exceptions import ProtocolError
from server import create_server


class ProtocolTests(unittest.TestCase):
    def test_encode_decode_message(self):
        message = protocol.make_request("get", {"id": 1, "title": "Задача"})
        raw = protocol.encode(message)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(protocol.decode(raw.strip()), message)

    def test_invalid_messages(self):
        with self.assertRaises(ProtocolError):
            protocol.decode(b"{not json")
        with self.assertRaises(ProtocolError):
            protocol.parse_request({"data": {}})


class IntegrationTests(unittest.TestCase):
    """Client -> TCP -> Server -> Service -> Repository."""

    @classmethod
    def setUpClass(cls):
        cls.server = create_server(port=0, udp_port=None)
        cls.server.start()
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_full_cycle(self):
        with TaskClient(port=self.server.port) as client:
            created = client.request("create", {"title": "Новая", "priority": "critical",
                                                "assignee": "Бурунд"})
            self.assertEqual(client.request("get", {"id": created["id"]})["title"], "Новая")
            critical = client.request("filter_by_priority", {"priority": "critical"})
            self.assertIn(created["id"], [t["id"] for t in critical])
            client.request("delete", {"id": created["id"]})
            with self.assertRaises(ServerError):
                client.request("get", {"id": created["id"]})
            with self.assertRaises(ServerError):
                client.request("fly")

    def test_three_clients(self):
        clients = [TaskClient(port=self.server.port) for _ in range(3)]
        for client in clients:
            client.connect()
        try:
            for number, client in enumerate(clients):
                client.request("create", {"title": f"От клиента {number}", "assignee": "X"})
            titles = [t["title"] for t in clients[0].request("list")]
            for number in range(3):
                self.assertIn(f"От клиента {number}", titles)
        finally:
            for client in clients:
                client.close()

    def test_timeout(self):
        # «Молчащий» сервер: принимает соединение, но не отвечает
        silent = socket.socket()
        silent.bind(("127.0.0.1", 0))
        silent.listen()
        try:
            client = TaskClient(port=silent.getsockname()[1], timeout=0.3)
            client.connect()
            with self.assertRaises(socket.timeout):
                client.request("list")
            client.close()
        finally:
            silent.close()


if __name__ == "__main__":
    unittest.main()
