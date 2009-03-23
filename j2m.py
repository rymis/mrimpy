#!/usr/bin/env python
# -*- coding: utf-8 -*-

" MailRu gateway main "

from xmpp import *
import mrim
import eserver

class MRIMGW(ProtocolProxy):
	def __init__(self):
		super(MRIMGW, self).__init__()

		self.mrim_user = None
		self.mrim = mrim.MailRuAgent()

		self.mrim.add_handler('hello_ack', self.h_hello_ack)
		self.mrim.add_handler('contact_list', self.h_contact_list)
		self.mrim.add_handler('user_status', self.h_user_status)
		self.mrim.add_handler('message', self.h_message)
		self.mrim.add_handler('login_success', self.h_login_success)
		self.mrim.add_handler('login_reject', self.h_login_reject)
		self.mrim.add_handler('user_info', self.h_user_info)

		self._clist = None
		self._creq_id = None
		self._vreq_id = None
		self._FN = None

	def auth(self, user, password):
		# Connect to server:
		self.mrim.connect()
		self._auth = (user, password)

	def vCardRequest(self, id):
		self._vreq_id = id
		if self._FN:
			self._send_vcard()

	def rosterRequest(self, id):
		self._creq_id = id
		if self._clist:
			self._send_contact_list()

	def presence(self, type, xml):
		if type == 'unavailable':
			status = mrim.STATUS_OFFLINE
		elif xml['show'] and xml['show'].nodes[0] == 'away':
			status = mrim.STATUS_AWAY
		else:
			status = mrim.STATUS_ONLINE

		self.mrim.change_status(status)


	def message(self, msg):
		print msg.toString()
		msg_to = msg.attrs['to']
		msg.attrs['from'] = self.user
		del msg.attrs['to']

		# Searching for msg_to session:
		for c in self.server.server.clients:
			if c.proxy.user == msg_to:
				c.send(msg.toString(pack=True))

	def pollRegister(self, poll):
		self.mrim.pollRegister(poll)

	def h_hello_ack(self):
		(user, password) = self._auth
		self._auth = None
		self.mrim_user = "%s@%s" % (user, self.server.from_)
		self.mrim.login(self.mrim_user, password)

	def h_contact_list(self, grps, cl):
		self._clist = (grps, cl)
		if self._creq_id:
			self._send_contact_list()

	def h_user_status(self, user, status):
		s = status
		if s == mrim.STATUS_OFFLINE:
			st = 'unavailable'
			show = None
		elif s == mrim.STATUS_ONLINE:
			st = 'online'
			show = None
		elif s == mrim.STATUS_AWAY:
			st = 'online'
			show = 'away'
		elif s == mrim.STATUS_UNDETERMINATED:
			st = 'unavailable'
			show = None
		else:
			st = 'unavailable'
			show = None
		self.server.sendPresence(user, st, show = show)

	def h_message(self, msg):
		pass

	def h_login_success(self):
		self.server.authSuccess()

	def h_login_reject(self, reason):
		self.server.authReject()

	def h_user_info(self, info):
		self._FN = info['MRIM.NICKNAME'].decode(mrim.MRIM_ENCODING)
		if _vreq_id:
			self._send_vcard()

	def _send_vcard(self):
		self.server.sendVCard(self._vreq_id, {'FN': self._FN})

	def _send_contact_list(self):
		print "Sending contact list..."
		cl = self._clist
		r = []
		for c in cl[1]:
			addr = c['address']
			nick = c['nick']
			if c['server_flags'] & mrim.CONTACT_INTFLAG_NOT_AUTHORIZED:
				subscr = 'from'
			elif c['flags'] & mrim.STATUS_UNDETERMINATED:
				subscr = 'to'
			else:
				subscr = "both"

			if c['group'] < len(cl[0]):
				grp = cl[0][c['group']]['name']
			else:
				grp = None

			r.append( [addr, nick, subscr, grp] )

		self.server.sendRoster(self._creq_id, r)
		for c in cl[1]:
			self.h_user_status(c['address'], c['status'])

if __name__ == '__main__':
	J = eserver.EventServer(('localhost', 5222), JabberServer, [MRIMGW])
	try:
		J.start()
	except:
		print_exc()
		J.stop()

