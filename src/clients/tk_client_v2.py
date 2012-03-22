__author__ = 'Daniel'

import json
import time
import getpass
import sys
from os.path import abspath

p = abspath('..')
if p not in sys.path:
    sys.path.append(p)

from twisted.internet import reactor, protocol, tksupport, task

from pgpu.compatibility import input, Print
import pgpu.tkinter2x as tk
from pgpu.tk_utils import SConsole, STextPlus
from pgpu.tkinter2x.constants import *

from common import ENCODER, JSONReceiver, I_LEAVE, I_JOIN


BECAUSE = ' because: "%s"'
FAIL = '*** The server was unable to carry out a request%s'
REJECTED = '*** The server dropped the connection%s'
AUTHED = '*** You have successfully authenticated to the Lila server.'
NO_CON = '*** %s is talking to you, you may wish to open a conversation.'
JOINED = '*** %s has joined the conversation.'
LEFT = '*** %s has left the conversation.'
LEFT_NO_CON = '*** %s has closed the conversation.'
MSG = '%(t)s <%(f)s> %(m)s'


class TKLilaLauncher(tk.Frame):
    '''
    The main launcher.
    '''
    def __init__(self, master, protocol, host):
        tk.Frame.__init__(self, master)
        
        self.c_val = tk.StringVar()
        
        e = tk.Entry(self, textvariable=self.c_val)
        e.pack(side=TOP, expand=True, fill=X)
        e.bind('<Return>', self.launch)
        
        sys.stdout = SConsole(self, wrap=WORD)
        # Don't scream, OK? :P
        sys.stdout.pack(side=TOP)
        
        self.host = host
        self.proto = protocol
    
    def launch(self, e):
        u = self.c_val.get().strip()
        if u:
            TKLilaDisplay(self.proto, self.host, u)
        self.c_val.set('')
    
    def quitter(self):
        self.proto.esend({'DC': True})
        self.destroy()


class TKLilaDisplay(tk.Toplevel):
    '''
    One of these is created for every conversation.
    '''
    def __init__(self, protocol, host, contact):
        tk.Toplevel.__init__(self)
        self.title('%s@%s|%s' % (protocol.user, host, contact))
        self.protocol('WM_DELETE_WINDOW', self.leave_conversation)
        
        self.disp = SConsole(self, height=15, wrap=WORD)
        self.disp.pack(side=TOP)
        
        tk.Button(self, text='Send', command=self.send_msg).pack(
                side=TOP, expand=True, fill=X)
        
        self.text = STextPlus(self, height=5, wrap=WORD)
        self.text.pack(side=TOP)
        
        self.contact = contact
        self.proto = protocol
        
        self.join_conversation()
    
    def send_msg(self):
        msg = self.text.gettext().strip()
        if not msg:
            return
        self.proto.say(self.contact, msg)
        self.text.clear()
    
    def join_conversation(self):
        self.proto.join_conversation(self)
    def leave_conversation(self):
        self.proto.leave_conversation(self)
        self.destroy()


class LilaClientProtocol(JSONReceiver):
    delimiter = '\n'    # Unused
    
    def __init__(self):
        self.authed = False
        self.conversations = {}

    def form_time(self, t):
        return time.strftime('%H:%M:%S', time.localtime(t))

    def connectionMade(self):
        data = {'USER': self.user, 'PASS': ENCODER(self.factory.pswd)}
        self.sendLine(json.dumps(data))
    
    def connectionLost(self, reason):
        Print('*** LOST CONNECTION TO SERVER: "%s"' % reason.getErrorMessage(),
                file=sys.__stdout__)
        sys.exit(1)

    def lineReceived(self, line):
        line = line.rstrip('\r')
        msg = json.loads(line)
        if msg.get('PING') is not None:
            self.sendLine(json.dumps({'PONG': msg['PING']}))
        if msg.get('STATUS') is not None:
            self.handle_status(msg)
        if msg.get('MSG') is not None:
            self.handle_msg(msg)
        if msg.get('NAMES') is not None:
            self.handle_names(msg)
        if msg.get('INFO') is not None:
            self.handle_info(msg)
    
    ### Message handlers
    
    def handle_status(self, msg):
        end = BECAUSE % msg['INFO'] if msg.get('INFO') else '.'
        
        if msg['STATUS'] == 'FAIL':
            Print(FAIL % end)
        elif msg['STATUS'] == 'REJECTED':
            Print(REJECTED % end)
            for c in self.conversations.values():
                self.leave_conversation(c)
        
        elif msg['STATUS'] == 'OK' and not self.authed:
            self.authed = True
            Print(AUTHED)
    
    def handle_msg(self, msg):
        t = self.form_time(msg['TIME'])
        f = msg['FROM']
        
        if f == self.user:
            where = self.conversations[msg['TO']].disp
        elif f in self.conversations:
            where = self.conversations[f].disp
        else:
            print(NO_CON % f)
            where = sys.stdout
        
        Print(MSG % dict(t=t, f=f, m=msg['MSG']), file=where)
    
    def handle_info(self, msg):
        f, i = msg['FROM'], msg['INFO']
        c = self.conversations.get(f)
        if c:
            if i == I_JOIN:
                Print(JOINED % f, file=c.disp)
            elif i == I_LEAVE:
                Print(LEFT % f, file=c.disp)
        elif i == I_LEAVE:
            Print(LEFT_NO_CON % f)
    
    ### External Interface
    
    def say(self, whom, what):
        if whom != self.user:
            self.esend({'FROM': self.user, 'TIME': time.time(), 'TO': whom, 
                    'MSG': what})
    
    def join_conversation(self, front):
        self.conversations[front.contact] = front
        self.esend({'INFO': I_JOIN, 'TO': front.contact, 'FROM': self.user})
    
    def leave_conversation(self, front):
        del self.conversations[front.contact]
        self.esend({'INFO': I_LEAVE, 'TO': front.contact, 'FROM': self.user})


class LilaTKClientFactory(protocol.ClientFactory):
    protocol = LilaClientProtocol
    def __init__(self, user, pswd, win):
        self.user = user
        self.pswd = pswd
        self.tk = win
    
    def buildProtocol(self, addr):
        p = protocol.ClientFactory.buildProtocol(self, addr)
        p.user = self.user
        
        l = TKLilaLauncher(self.tk, p, addr.host)
        self.tk.protocol('WM_DELETE_WINDOW', l.quitter)
        l.pack()
        
        return p


if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = sys.argv[2] if len(sys.argv) > 2 else 55555
    user = input('Lila username for %s: ' % host)
    pswd = getpass.getpass('Lila password for %s: ' % user)
    
    win = tk.Tk()
    win.title('Lila: %s@%s' % (user, host))
    
    tksupport.install(win)
    
    reactor.connectTCP(host, port, 
            LilaTKClientFactory(user, pswd, win))
    reactor.run()
