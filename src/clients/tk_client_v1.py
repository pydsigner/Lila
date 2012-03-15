# Written by pydsigner
from __future__ import print_function
import sys
import json
import time
import getpass
import os

import pgpu.tkinter2x as tk
from pgpu.tk_utils import SConsole
from pgpu.tkinter2x.constants import *

from twisted.internet import reactor, protocol, tksupport, task
from twisted.protocols import basic

BECAUSE = ' because: "%s"'
FAIL = '*** The server was unable to carry out a request%s'
REJECTED = '*** The server dropped the connection%s'
AUTHED = '*** You have successfully authenticated to the Lila server.'

try:
    input = raw_input
except NameError:
    pass

class SList(tk.Frame):
    """
    Based on Mark Lutz's ScrolledList() widget from Programming Python, 
    3rd edition.
    """
    def __init__(self, master):
        tk.Frame.__init__(self, master)
        
        sbar = tk.Scrollbar(self)
        l = tk.Listbox(self, relief=SUNKEN)
        
        sbar.config(command=l.yview)
        l.config(yscrollcommand=sbar.set)
        
        sbar.pack(side=RIGHT, fill=Y)
        l.pack(side=LEFT, expand=YES, fill=BOTH)
        
        self.listbox = l
    
    def set(self, l):
        self.listbox.delete(0, END)
        self.listbox.insert(END, *l)

class TKLilaDisplay(tk.Frame):
    def __init__(self, master, protocol):
        tk.Frame.__init__(self, master)
        
        self.msg_var = tk.StringVar()
        self.target_var = tk.StringVar()
        eframe = tk.Frame(self)
        
        e1 = tk.Entry(eframe, textvariable = self.target_var)
        e1.pack(side = LEFT, fill = X)
        e2 = tk.Entry(eframe, textvariable = self.msg_var)
        e2.pack(side = RIGHT, expand = YES, fill = X)
        
        eframe.pack(side = BOTTOM, expand = YES, fill = X)
        
        e1.bind('<Return>', self.send_msg)
        e2.bind('<Return>', self.send_msg)
        
        self.slist = SList(self)
        self.slist.pack(side = RIGHT, expand = YES, fill = BOTH)
        
        display = SConsole(self)
        display.pack(side = LEFT)
        sys.stdout = display        
        
        self.protocol = protocol
    
    def send_msg(self, *args):
        msg, to = self.msg_var.get().strip(), self.target_var.get().strip()
        if not (msg or to):
            return
        self.protocol.say(to, msg)
        self.msg_var.set('')

class LilaClientProtocol(basic.LineReceiver):
    delimiter="\n"
    
    def __init__(self):
        self.authed = False

    def form_time(self, t):
        return time.strftime('%H:%M:%S', time.localtime(t))

    def connectionMade(self):
        data = {"USER" : self.factory.user, "PASS" : self.factory.pswd}
        self.sendLine(json.dumps(data))
    
    def connectionLost(self, reason):
        print('*** LOST CONNECTION TO SERVER: "%s"' % 
                reason.getErrorMessage())
        sys.exit(1)

    def lineReceived(self, line):
        line = line.rstrip("\r")
        msg = json.loads(line)
        if msg.get('PING'):
            self.sendLine(json.dumps({'PONG': msg['PING']}))
        if msg.get('STATUS'):
            self.handle_status(msg)
        if msg.get('MSG'):
            self.handle_msg(msg)
        if msg.get('NAMES'):
            self.handle_names(msg)
    
    def handle_status(self, msg):
        end = BECAUSE % msg['INFO'] if msg.get('INFO') else '.'
        
        if msg['STATUS'] == 'FAIL':
            print(FAIL % end)
        elif msg['STATUS'] == 'REJECTED':
            print(REJECTED % end)
        
        elif msg['STATUS'] == 'OK' and not self.authed:
            self.authed = True
            print(AUTHED)
    
    def handle_msg(self, msg):
        if msg['FROM'] == self.factory.user:
            msg['FROM'] = '@' + msg['TO']
        print('%s <%s> %s' % (
                self.form_time(msg['TIME']), msg['FROM'], msg['MSG']))
        
    #### External Interface
    
    def say(self, whom, what):
        if whom != self.factory.user:
            self.sendLine(json.dumps({'FROM': self.factory.user, 'TIME': time.time(), 
                    'TO': whom, 'MSG': what}))


class LilaTKClientFactory(protocol.ClientFactory):
    protocol = LilaClientProtocol
    def __init__(self, user, pswd, win):
        self.user = user
        self.pswd = pswd
        self.tk = win
    
    def buildProtocol(self, addr):
        p = protocol.ClientFactory.buildProtocol(self, addr)
        TKLilaDisplay(self.tk, p).pack(expand = YES, fill = BOTH)
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
