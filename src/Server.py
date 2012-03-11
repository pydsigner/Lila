__author__ = 'Jakob'

from twisted.protocols.basic import LineReceiver
from twisted.internet.protocol import Factory
from twisted.internet import reactor
from twisted.python import log
#from database import redis_database as database
from database import test_dabase as database
import uuid
import json
import sys

def shutdownOnError(message):
    """Die hard on any exceptions in the program."""
    if message["isError"]:
        reactor.stop()


class Server(LineReceiver):
    def __init__(self):
        self.state = "PRE_AUTH"
        self.last_ping = None
        self.alive = True

    def lineReceived(self, line):
        """Handle a line that just came down the pipe, dispatch it depending on our state and the contents."""
        try:
            data = json.loads(line)
        except Exception:
            self.reject_kindly_with_msg("Unable to decode?")
            return
        if self.state == "PRE_AUTH":
            self.handle_auth(data)
        if data.get("PONG"):
            self.handle_pong(data)
        if data.get("MSG"):
            self.handle_msg(data)
        if data.get("DC"):
            self.handle_dc(data)

    def handle_pong(self, data):
        """Handle a PING response. If its not a match then die hard and fast."""
        if data.get("PONG") != self.last_ping.get("PING"):
            self.transport.loseConnection()
        else:
            self.alive = True

    def handle_msg(self, data):
        """
        Handle a message, if its addressed to someone then post it to them,
        otherwise tell my client that they are not online
        """
        target = self.factory.connections[data.get("TO", None)]
        if target is None:
            response = {"STATUS": "FAIL", "INFO": "Failed to find partner online."}
            self.sendLine(json.dumps(response))
        else:
            target.sendLine(json.dumps(data))

    def handle_auth(self, data):
        """
        Authenticate a user. See if the user:password pair match what we have in the database.
        If this is the case then tell them its good, update their state, otherwise reject them.
        """
        user = data.get("USER")
        password = data.get("PASS")
        if database.authenticate_user(user, password):
            response = {"STATUS": "OK"}
            self.sendLine(json.dumps(response))
            self.user = user
            self.factory.connections.pop(self.hostname)
            self.factory.connections[self.user] = self
            self.state = "LIVE"
            log.msg("Authenticated user %s. All is well, connections dict updated." % self.hostname)
        else:
            log.msg("%s failed to authenticated, dropping their connection." % self.hostname)
            self.reject_kindly()

    def heartbeat(self):
        if not self.alive:
            self.reject_kindly_with_msg("Did not reply to last ping.")
            return
        log.msg("Sending heartbeat.")
        self.last_ping = {"PING": uuid.uuid4().hex}
        self.sendLine(json.dumps(self.last_ping))
        self.alive = False # schrodinger's cat, lets assume the client is dead until they tell us otherwise
        self.beat = reactor.callLater(25, self.heartbeat)

    def connectionLost(self, reason):
        self.factory.clients -= 1
        try:
            self.factory.connections.pop(self.hostname)
        except KeyError:
            # Could be they are stored under the username not their hostname.
            self.factory.connections.pop(self.user)

    def reject_kindly(self):
        log.msg("Rejected client: %s" % self.hostname)
        answer = {"STATUS": "REJECTED"}
        self.sendLine(json.dumps(answer))
        # Grace period for killing the connection.
        reactor.callLater(1.5, self.transport.loseConnection)

    def reject_kindly_with_msg(self, msg):
        log.msg("Rejected client: %s for reason %s" % (self.user, msg))
        answer = {"STATUS": "REJECTED", "INFO": msg}
        self.sendLine(json.dumps(answer))
        # Grace period for killing the connection.
        reactor.callLater(1.5, self.transport.loseConnection)

    def authed_in_time(self):
        """
        The user failed to send the right authentication inside of the 20 second time limit.
        """
        if self.state != "LIVE":
            log.msg("Disconnecting user %s for failing to authenticate in-time" % self.hostname)
            self.reject_kindly()

    def connectionMade(self):
        self.state = "PRE_AUTH"
        self.hostname = self.transport.getHost().host
        log.msg(self.hostname)
        if self.hostname not in self.factory.connections:
            self.factory.connections[self.hostname] = self
            self.factory.clients += 1
        else:
            self.reject_kindly()
        reactor.callLater(20, self.authed_in_time)
        reactor.callLater(25, self.heartbeat)


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