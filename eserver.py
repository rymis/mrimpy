#!/usr/bin/env python

"""
	Event-based TCP server implementation
"""

import select
import socket
from traceback import print_exc

class Protocol(object):
	" Application protocol implementation "

	def __init__(self, sock, server):
		" Init protocol. "
		self.sock = sock
		self.server = server
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

	def pollRegister(self, poll):
		" Register editional events in poll "
		pass

class Poll(object):
	" Hi-level select mechanism wrapper "

	def __init__(self):
		" Create new Poll object "
		self._peers = []

	def register(self, sock, read_f = None, write_f = None, err_f = None, args = None):
		" Register or modify polling socket "
		if hasattr(sock, "fileno"):
			sock = sock.fileno()

		# search for peer:
		for p in self._peers:
			if p[0] == sock:
				p[1] = read_f
				p[2] = write_f
				p[3] = err_f
				p[4] = args
				return

		self._peers.append( (sock, read_f, write_f, err_f, args) )

	def unregister(self, sock):
		" Remove socket from list "
		if hasattr(sock, "fileno"):
			sock = sock.fileno()
		for i in xrange(len(self._peers)):
			if self._peers[i][0] == sock:
				del self._peers[i]
				break

	def poll(self, timeout = -1):
		" select active sockets "
		pl = select.poll()
		for p in self._peers:
			mask = 0
			if p[1]:
				mask |= select.POLLIN | select.POLLPRI
			if p[2]:
				mask |= select.POLLOUT
			if p[3]:
				mask |= select.POLLERR

			pl.register(p[0], mask)

		res = pl.poll(timeout)

		for r in res:
			peer = None
			for p in self._peers:
				if r[0] == p[0]:
					peer = p

			if peer:
				if r[1] & select.POLLIN:
					if peer[4]:
						peer[1](*peer[4])
					else:
						peer[1]()
				if r[1] & select.POLLOUT:
					if peer[4]:
						peer[2](*peer[4])
					else:
						peer[2]()
				if r[1] & select.POLLERR:
					if peer[4]:
						peer[3](*peer[4])
					else:
						peer[3]()

		del pl

class EventServer(object):
	def __init__(self, addr, handle_class, eargs = None):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.sock.bind(addr)
		self.clients = []
		self.poll_timeout = -1
		self.eargs = eargs

		self.handle_class = handle_class
		self._stop = False

	def start(self):
		" Start server "
		self.sock.listen(5)

		while not self._stop:
			p = Poll()
			p.register(self.sock, read_f = self._accept_client)

			for cl in self.clients:
				if len(cl.queue) > 0:
					p.register(cl, read_f = self._read_cl, write_f = self._write_cl, args = [cl])
				else:
					p.register(cl, read_f = self._read_cl, args = [cl])

				cl.pollRegister(p)

			p.poll(self.poll_timeout)

			if self.poll_timeout > 0:
				for cl in self.clients:
					cl.idle()

		self.sock.close()

	def _write_cl(self, cl):
		d = cl.queue[0]
		l = cl.sock.send(d)
		if l < len(d):
			cl.queue[0] = d[l:]
		else:
			del cl.queue[0]

	def _read_cl(self, cl):
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
			print_exc()
			cl.sock.close()
			self.removeClient(cl)

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
			args = [s[0], self]
			if self.eargs:
				args.extend(self.eargs)
				
			cl = self.handle_class(*args)
			self.clients.append(cl)
		except:
			print_exc()

	def _client_by_fileno(self, fno):
		for c in self.clients:
			if c.fileno() == fno:
				return c
		return None
