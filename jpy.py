#!/usr/bin/env python

" Simple jabber server implementation. It is for example only. "

from xmpp import *
import eserver

class UserList(object):
	def __init__(self):
		self.users = [
			( 'test1', 'test1' ),
			( 'test2', 'test2' ),
			( 'test3', 'test3' )
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

	def auth(self, user, password):
		if self.server.from_ != self.domain or not self.users.auth(user, password):
			print "Authorization failed: %s@%s" % (user, self.server.from_)
			self.server.authReject()
		else:
			self.server.authSuccess()

	def vCardRequest(self, id):
		info = { }
		info['FN'] = self.server.user
		self.server.sendVCard(id, info)

	def rosterRequest(self, id):
		r = []
		for u in self.users.users:
			if u[0] != self.server.user:
				r.append( (u[0], u[0], 'both', 'GROUP') )

		self.server.sendRoster(id, r)

if __name__ == '__main__':
	J = eserver.EventServer(('localhost', 5222), JabberServer, [SimpleJServer])
	try:
		J.start()
	except:
		print_exc()
		J.stop()

