__author__ = 'Jakob'
import uuid
import json
import sys
from os.path import abspath

p = abspath('..')
if p not in sys.path:
    sys.path.append(p)

from twisted.internet.protocol import Factory
from twisted.internet import reactor
from twisted.python import log

from common import JSONReceiver


def shutdownOnError(message):
    """
    Die hard on any exceptions in the program.
    """
    if message["isError"]:
        reactor.stop()


class Server(JSONReceiver):
    """
    The server for the protocol, handles heartbeats, authentication and handle 
    dispatching of any JSON data getting sent to it, based on the Twisted 
    LineReciever it takes single \n delimited lines over the net.
    """
    delimiter = "\n"
    def __init__(self):
        self.state = "PRE_AUTH"
        self.last_ping = None
        self.alive = True
        self.beat = None
        self.user = None

    def lineReceived(self, line):
        """
        Handle a line that just came down the pipe, dispatch it depending on 
        our state and the contents.
        """
        try:
            # Rip off the linux carriage return
            line = line.rstrip("\r")
            log.msg(repr(line))
            data = json.loads(line)
        except ValueError, e:
            # Its an error, let's post it back.
            self.esend({"STATUS": "ERR", "INFO": str(e)})
        
        if self.state == "PRE_AUTH":
            self.handle_auth(data)
        if data.get("PONG") is not None:
            self.handle_pong(data)
        if data.get("MSG") is not None:
            self.handle_msg(data)
        if data.get("DC") is not None:
            self.handle_dc(data)
        if data.get("INFO") is not None:
            self.handle_info(data)

    def handle_dc(self, data):
        """
        The user wants to disconnect. Clean up.
        """
        self.beat.cancel()
        self.transport.loseConnection()

    def handle_info(self, data):
        """
        Write a neater and smarter information API.
        """
        target = self.factory.connections.get(data.get("TO"))
        if target:
            target.esend(data)

    def handle_pong(self, data):
        """
        Handle a PING response. If its not a match then drop the connection.
        They probably timed out or have network issues.
        """
        if data.get("PONG") != self.last_ping.get("PING"):
            self.transport.loseConnection()
        else:
            log.msg("Got valid PONG from %s" % self.user)
            self.alive = True

    def handle_msg(self, data):
        """
        Handle a message, if its addressed to someone then post it to them,
        otherwise tell my client that they are not online
        """
        target = self.factory.connections.get(data.get("TO"))
        if target is None:
            self.esend({"STATUS": "FAIL", 
                    "INFO": "Failed to find partner online."})
        else:
            target.esend(data)
            self.esend(data)

    def handle_auth(self, data):
        """
        Authenticate a user. See if the user:password pair match what we have 
        in the database. If this is the case, then tell them it's good and 
        update their state, otherwise reject them.
        """
        user = data.get("USER")
        password = data.get("PASS")
        authed, status = self.factory.database.authenticate_user(user, password)
                
        if authed:
            response = {"STATUS": "OK"}
            self.esend(response)
            self.user = user
            self.factory.connections.pop(self.hostname)
            self.factory.connections[self.user] = self
            self.state = "LIVE"
            log.msg("Authenticated user %s. All is well, connections dict updated." % self.hostname)
        else:
            log.msg("%s failed to auth with code %s, dropping their connection." % (self.hostname, status))
            self.reject_kindly_with_msg("Failed to auth")

    def heartbeat(self):
        """
        See if the connected client managed to reply to the last ping, if they 
        didn't give up. Otherwise post off a new ping, pretend they are dead 
        till we find out otherwise, then call ourselves again in another 25 
        seconds.
        """
        if not self.alive:
            self.reject_kindly_with_msg("Did not reply to last ping.")
            return
        log.msg("Sending heartbeat.")
        self.last_ping = {"PING": uuid.uuid4().hex}
        self.esend(self.last_ping)
        # Schrodinger's cat, let's assume the client is dead,
        # until they tell us otherwise
        self.alive = False 
        self.beat = reactor.callLater(25, self.heartbeat)

    def connectionLost(self, reason):
        """
        Handles the connectionLost event.
        When the connection is lost decrement the number of clients.
        Then pop off the key, value in the connections dict, remember they 
        might not have authed yet so we have to try pop()ing both values
        """
        self.factory.clients -= 1
        try:
            self.factory.connections.pop(self.user)
        except KeyError:
            # Could be they are stored under the username not their hostname.
            try:
                self.factory.connections.pop(self.hostname)
            except KeyError:
                log.msg(self.factory.connections)

    def reject_kindly(self):
        """
        Let the client know they are going to get cut off.
        """
        try:
            self.beat.cancel() # might be before or after the heartbeat.
        except AttributeError, e:
            pass
        log.msg("Rejected client: %s" % self.hostname)
        self.esend({"STATUS": "REJECTED"})
        # Grace period for killing the connection.
        reactor.callLater(1.5, self.transport.loseConnection)

    def reject_kindly_with_msg(self, msg):
        """
        Reject the client but this time with a nice pretty message.
        """
        try:
            self.beat.cancel()
        except Exception:
            pass
        log.msg("Rejected client: %s for reason %s" % (self.hostname, msg))
        answer = {"STATUS": "REJECTED", "INFO": msg}
        self.esend(answer)
        # Grace period for killing the connection.
        reactor.callLater(1.5, self.transport.loseConnection)

    def authed_in_time(self):
        """
        Check to see if the user failed to send the right authentication inside 
        of the 20 second time limit.
        """
        if self.state != "LIVE":
            log.msg("Disconnecting user %s for failing to authenticate in-time" % self.hostname)
            self.reject_kindly()

    def connectionMade(self):
        """
        Connection has been made, set PRE_AUTH state, get our hostname and then 
        assign ourselves to the connections. 25 seconds later, we start the 
        heartbeat; This gives enough time for authentication.
        """
        self.state = "PRE_AUTH"
        self.hostname = self.transport.getHost().host
        log.msg(self.hostname)
        if self.hostname not in self.factory.connections:
            self.factory.connections[self.hostname] = self
            self.factory.clients += 1
        else:
            self.reject_kindly()
        reactor.callLater(20, self.authed_in_time)
        self.beat = reactor.callLater(25, self.heartbeat)
        log.msg(self.factory.connections)


class ServerFactory(Factory):
    protocol = Server

    def __init__(self, database):
        self.connections = {}
        self.database = database
        self.clients = 0
        self.user = None


def main(port, database=None, debug=False, stdout=True):
    if stdout:
        log.startLogging(sys.stdout)
    if debug:
        log.addObserver(shutdownOnError)
    reactor.listenTCP(port, ServerFactory(database))
    reactor.run()


if __name__ == '__main__':
    print "Don't run me."
