#!/usr/bin/env python

import eserver
import socket
from traceback import print_exc

class Proxy(eserver.Protocol):
	def __init__(self, sock, server, addr):
		super(Proxy, self).__init__(sock, server)
		self.addr = addr
		self.peer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.peer.connect(addr)
		self._peer_queue = []

	def processData(self, data):
		self._peer_queue.append(data)

	def pollRegister(self, poll):
		if len(self._peer_queue) > 0:
			w_f = self._write_p
		else:
			w_f = None

		poll.register(self.peer, read_f = self._read_p, write_f = w_f)

	def _read_p(self):
		# Read from peer:
		buf = self.peer.recv(1024)

		if len(buf) == 0:
			self.close()
			return

		# And send to client:
		self.send(buf)

	def _write_p(self):
		# Send first item from write queue:
		l = self.peer.send(self._peer_queue[0])
		if l < 0:
			raise IOError, "Can not write"
		if l < len(self._peer_queue[0]):
			self._peer_queue[0] = self._peer_queue[0][l:]
		else:
			del self._peer_queue[0]


if __name__ == '__main__':
	S = eserver.EventServer( ('localhost', 9999), Proxy, eargs = [ ('www.google.com', 80) ] )
	try:
		S.start()
	except:
		print_exc()
		S.stop()


