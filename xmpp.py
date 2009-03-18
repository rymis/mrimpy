#!/usr/bin/env python

import xmlstream
import socket

class XMPPError(Exception):
	pass

class XMPPClient(object):
	" Jaber client representation "
	def __init__(self, sock):
		self.sock = sock

	def close(self):
		" Send </stream> and close connection "
		self.sock.close()

	def fileno(self):
		return self.sock.fileno()

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
		pass

	def stop(self):
		" Stop server "
		pass

	def register_plugin(self, p):
		" Register new plugin "
		self.plugins.append(p)
		p.register(self)

