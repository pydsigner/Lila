import unittest
import subprocess
import socket
import json
import sys

class Server_Test(unittest.TestCase):
    def setUp(self):
        self.server = subprocess.Popen(["python", "../src/server.py"], stdout=sys.stdout, stderr=subprocess.PIPE)
        self.client = socket.socket()
        self.client.connect(("127.0.0.1", 555))

    def new_user(self):
        self.client.close()
        self.client = socket.socket()
        self.client.connect(("127.0.0.1", 555))

    def test_auth(self):
        """Assert the test user can connect and gets the correct response"""
        self.new_user()
        data = {"USER": "test", "PASS": "test"}
        self.client.send(json.dumps(data) + "\n")
        buf = []
        while buf[-1:] != [b'\n']:
            buf.append(self.client.recv(1))
        response = ''.join(buf).decode()
        print response
        self.assertEqual(json.loads(response), {"STATUS": "OK"})
