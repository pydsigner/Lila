__author__ = 'Jakob'

from twisted.protocols.basic import LineReceiver
from twisted.internet.protocol import Factory
from twisted.internet import reactor
from twisted.python import log
import time
import json
import sys

def shutdownOnError(message):
    if message["isError"]:
        reactor.stop()

class Server(LineReceiver):
    def lineReceived(self, line):
        if self.state == "PRE_AUTH":
            self.handle_auth(line)
        else:
            self.handle_line(line)

    def handle_line(self, line):
        pass

    def handle_auth(self, line):
        pass

    def heartbeat(self):
        #noinspection PyTypeChecker
        self.sendLine(time.asctime())
        reactor.callLater(5, self.heartbeat)

    def connectionLost(self, reason):
        self.factory.clients -= 1
        self.factory.connections.pop(self.hostname)

    def reject_kindly(self):
        answer = {"STATUS" : "CONNECTION_REJECTED"}
        self.sendLine(json.dumps(answer))
        # Grace period for killing the connection.
        reactor.callLater(3, self.transport.loseConnection)

    def connectionMade(self):
        self.state = "PRE_AUTH"
        self.hostname = self.transport.getHost().host
        log.msg(self.hostname)
        if self.hostname not in self.factory.connections:
            self.factory.connections[self.hostname] = self
            self.factory.clients += 1
        else:
            self.reject_kindly()

class ServerFactory(Factory):
    protocol = Server
    def __init__(self):
        self.connections = {}
        self.clients = 0

if __name__ == '__main__':
    log.startLogging(sys.stdout)
    log.addObserver(shutdownOnError)
    reactor.listenTCP(555, ServerFactory())
    reactor.run()