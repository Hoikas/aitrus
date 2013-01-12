#!/usr/bin/env python3

import asynchat
import socket

class IRCBotBase:
    class _net_core(asynchat.async_chat):
        """Private net protocol implementation details"""
        def __init__(self, parent, host, port):
            self._parent = parent
            self.timeout = 180
            self.set_terminator(b"\r\n")
            self.connected = False
            self._incoming = []
    
            # asynchat socket init
            asynchat.async_chat.__init__(self)
            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connect((host, port))

        def collect_incoming_data(self, data):
            self._incoming.append(data)

        def send_cmd(self, msg):
            if self.connected:
                self.push(bytes(msg.join("\r\n"), "UTF-8"))
            else:
                raise NotConnectedError()

        def handle_close(self):
            raise NotImplementedError()

        def handle_connect(self):
            self.connected = True
            self.send_cmd("NICK %s" % self._parent._nick_name)
            self.send_cmd("USER aitrus 0 *:%s" % self._parent._real_name)
            self._parent.handle_connect()

        def handle_error(self):
            raise # we want detailed errors

        def found_terminator(self):
            def get_message(raw, data, start):
                trash = 1 # account for leading colon
                for i in range(start):
                    trash += len(data[i]) + 1 # account for space
                return raw[trash:]

            raw = (b"".join(self._incoming)).decode("UTF-8")
            self._incoming = []
            if raw.upper().startswith("PING"):
                self.send_cmd("PONG %s" % raw[5:])
                return
            data = raw.split()
            if len(data) < 3:
                # This message is screwed up (too short)
                return
            sender = data[0].split("!")[0][1:]
            cmd = data[1].upper()

            # Let the ugly ass parsing begin!
            if cmd.isdigit():
                pass # Later...
            elif cmd == "JOIN":
                channel = data[2][1:]
                self._parent._channels.append(channel)
                self._parent.handle_join(channel)
            elif cmd == "KICK":
                channel = data[2] # no leading colon
                reason = data[3][1:] # leading colon
                self._parent._channels = [i for i in self._parent._channels if i != channel]
                self._parent.handle_kick(channel, sender, reason)
            elif cmd == "PRIVMSG":
                msg = get_message(raw, data, 3)
                if msg.startswith("\u0001"):
                    if msg.startswith("\u0001ACTION"):
                        expand = "%s %s" % (sender, msg[8:len(msg)-1])
                        self._parent.handle_message(data[2], sender, expand)
                    else:
                        self._parent.handle_ctcp(sender, msg[1:len(msg)-1].upper())
                else:
                    self._parent.handle_message(data[2], sender, msg)


    _channels = []

    def __init__(self, host, port, nick="Aitrus", name="Aitrus Chat Bot"):
        self._imp = IRCBotBase._net_core(self, host, port)
        self._nick_name = nick
        self._real_name = name

    def handle_connect(self):
        pass

    def handle_ctcp(self, sender, msg):
        pass

    def handle_join(self, channel):
        pass

    def handle_kick(self, channel, oper, reason):
        pass

    def handle_message(self, channel, user, msg):
        pass

    def join_channel(self, channel):
        self._imp.send_cmd("JOIN %s" % channel)

    def _set_nick_name(self, nick):
        self._nick_name = nick
        try:
            self._imp.send_cmd("NICK %s" % nick)
        except NotConnectedError:
            pass # we'll set it when we connect
    def _get_nick_name(self):
        try:
            return self._nick_name
        except AttributeError:
            return None
    nick_name = property(_get_nick_name, _set_nick_name)

    def send_nctcp(self, destination, msg):
        self._imp.send_cmd("NOTICE %s :\u0001%s\u0001" % (destination, msg))

    def send_msg(self, destination, msg):
        self._imp.send_cmd("PRIVMSG %s :%s" % (destination, msg))

    def send_quit(self, msg):
        self._imp.send_cmd("QUIT :%s" % msg)

    def send_wallchan(self, msg):
        for chan in self._channels:
            self.send_msg(chan, msg)


class NotConnectedError(Exception):
    """This error is raised when you attempt to do an operation that requires
       a connection but no connection is established."""
    pass


# Test case
if __name__ == '__main__':
    import asyncore
    ass = IRCBotBase("irc.justirc.net", 6667)
    asyncore.loop()
