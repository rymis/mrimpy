#!/usr/bin/env python

import xmlstream
import socket
import select

class XMPPError(Exception):
	pass

class XMPPClient(object):
	" Jaber client representation "
	def __init__(self, sock):
		self.sock = sock
		self.queue = [] # Message queue

	def close(self):
		" Send </stream> and close connection "
		self.sock.close()

	def fileno(self):
		return self.sock.fileno()

	def data(self, buf):
		" data received "
		pass

class XMPPPlugin(object):
	" Handler of stanzas "
	STANZAS = []

	def register(self, server):
		" Register this plugin "
		self.server = server

	def unregister(self):
		" Unregister plugin "
		pass

	def process_stanza(self, xml, client):
		" Process stanza "
		pass

	def get_features(self):
		return None

class XMPPServer(object):
	def __init__(self, addr = ('127.0.0.1', 5221), no_register_defaults = False):
		self.sock = socket.socket(socket.SOCK_STREAM)
		self.sock.bind(addr)
		self.clients = []
		self.plugins = []

		if not no_register_defaults:
			for P in xmpp_plugins.PLUGINS:
				p = P()
				self.register_plugin(p)

	def start(self):
		" Start server "
		self.sock.listen(5)

		while True:
			# Take all sockets:
			p = select.poll()
			p.register(self.sock, select.POLLIN | select.POLLPRI)
			for c in self.clients:
				if len(c.queue) > 0:
					p.register(self.sock, select.POLLIN | select.POLLPRI | select.POLLOUT)
				else:
					p.register(self.sock, select.POLLIN | select.POLLPRI)

			r = p.poll(10)
			for c in r:
				if isinstance(c[0], socket.Socket):
					self.accept_client()
				else:
					if c[0] & select.POLLIN:
						buf = c.sock.recv(1024)
						c.data(buf)

	def stop(self):
		" Stop server "
		pass

	def register_plugin(self, p):
		" Register new plugin "
		self.plugins.append(p)
		p.register(self)

