#!/usr/bin/env python

" Simple jabber server implementation. It is for example only. "

from xmpp import *
import eserver

class UserList(object):
	def __init__(self):
		self.users = [
			[ 'test1', 'test1', 0 ],
			[ 'test2', 'test2', 0 ],
			[ 'test3', 'test3', 0 ]
		]

	def hasUser(self, name):
		for u in self.users:
			if u[0] == name:
				return True

		return False

	def auth(self, name, password):
		for u in self.users:
			if u[0] == name and u[1] == password:
				return True

		return False

	def getRoster(self, user):
		r = []
		for u in self.users:
			if u[0] != user:
				r.append( ("%s@%s" % (u[0], self.server.from_), u[0], 'both', 'GROUP') )
		return r

	def setOnline(self, user, online):
		for u in self.users:
			if u[0] == user:
				u[2] = online


__users = None
def GetUserList():
	global __users
	if not __users:
		__users = UserList()

	return __users

class SimpleJServer(ProtocolProxy):
	def __init__(self):
		super(SimpleJServer, self).__init__()
		self.users = GetUserList()
		self.domain = 'example.net'
		self.user = None
		self.online = None

	def auth(self, user, password):
		if self.server.from_ != self.domain or not self.users.auth(user, password):
			print "Authorization failed: %s@%s" % (user, self.server.from_)
			self.server.authReject()
		else:
			self.user = '%s@%s' % (user, self.server.from_)
			self.server.authSuccess()

	def vCardRequest(self, id):
		info = { }
		info['FN'] = self.server.user
		self.server.sendVCard(id, info)

	def rosterRequest(self, id):
		r = [u for u in self.users.getRoster(self.server.user)]
		self.server.sendRoster(id, r)

		for u in self.users.users:
			# is he online?
			if u[2]:
				self.server.sendPresence("%s@%s" % (u[0], self.server.from_), 'online')
			else:
				self.server.sendPresence("%s@%s" % (u[0], self.server.from_), 'unavailable')

	def presence(self, type, xml):
		if type != 'unavailable':
			self.online = True
		else:
			self.online = False

		self.users.setOnline(self.server.user, self.online)

		for c in self.server.server.clients:
			if c != self.server:
				c.sendPresence(self.user, type)

	def message(self, msg):
		print msg.toString()
		msg_to = msg.attrs['to']
		msg.attrs['from'] = self.user
		del msg.attrs['to']

		# Searching for msg_to session:
		for c in self.server.server.clients:
			if c.proxy.user == msg_to:
				c.send(msg.toString(pack=True))

if __name__ == '__main__':
	J = eserver.EventServer(('localhost', 5222), JabberServer, [SimpleJServer])
	try:
		J.start()
	except:
		print_exc()
		J.stop()

