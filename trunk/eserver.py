#!/usr/bin/env python

"""
	Event-based TCP server implementation
"""

import select
import socket

class Protocol(object):
	" Application protocol implementation "

	def __init__(self, sock, server):
		" Init protocol. "
		self.sock = sock
		self.queue = []

	def processData(self, data):
		" Main function. Process data, received from client "
		pass

	def connectionClosed(self):
		" Called when connection is closed "
		pass

	def idle(self):
		" Protocol can define idle function, that will be called one time per 10 millisecs "
		pass

	# After this point functions is not redefined:
	def send(self, buf):
		" Send data to client. Will send data only when possible "
		if len(buf) > 0:
			self.queue.append(buf)
		return len(buf)

	def close(self):
		" Close connection "
		self.sock.close()
		self.server.removeClient(self)

	def fileno(self):
		" Returns low-level file descriptor "
		return self.sock.fileno()

class EventServer(object):
	def __init__(self, addr, handle_class):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.bind(addr)
		self.clients = []
		self.idle_interval = 10

		self.handle_class = handle_class
		self._stop = False

	def start(self):
		" Start server "
		self.sock.listen(5)

		while not self._stop:
			p = select.poll()
			p.register(self.sock)

			for cl in self.clients:
				if len(cl.queue) > 0:
					p.register(cl, select.POLLIN | select.POLLPRI | select.POLLOUT)
				else:
					p.register(cl, select.POLLIN | select.POLLPRI)

			res = p.poll(self.idle_interval)
			for s in res:
				if s[0] == self.sock.fileno():
					self._accept_client()
				else:
					cl = self._client_by_fileno(s[0])
					if s[1] & select.POLLOUT:
						d = cl.queue[0]
						l = cl.sock.send(d)
						if l < len(d):
							cl.queue[0] = d[l:]
						else:
							del cl.queue[0]

					if s[1] & select.POLLIN:
						buf = cl.sock.recv(1024)
						if len(buf) == 0:
							print "Client closed connection:", cl
							cl.connectionClosed()
							cl.sock.close()
							self.removeClient(cl)
						try:
							cl.processData(buf)
						except:
							print "Client raised error: ", cl
							cl.sock.close()
							self.removeClient(cl)

			for cl in self.clients:
				cl.idle()

	def stop(self):
		" Stop server "
		self._stop = True

	def removeClient(self, cl):
		" Remove client from list of clients "
		self.clients.remove(cl)

	def _accept_client(self):
		try:
			s = self.sock.accept()
			print "New client from: ", s[1]
			cl = self.handle_class(s[0], self)
			self.clients.append(cl)
		except:
			pass

	def _client_by_fileno(self, fno):
		for c in self.clients:
			if c.fileno() == fno:
				return c
		return None
