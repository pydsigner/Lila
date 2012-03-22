import json

from twisted.protocols.basic import LineReceiver

from pgpu.security import fetcher


I_JOIN, I_LEAVE = range(2)

ENCODER = fetcher('sha512').encode
del fetcher


class JSONReceiver(LineReceiver):
    def esend(self, obj):
        self.sendLine(json.dumps(obj))
