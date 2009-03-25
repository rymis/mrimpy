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
		self.mrim.add_handler('connection_closed', self.h_connection_closed)
		self.mrim.add_handler('authorization_request', self.h_authorization_request)
		self.mrim.add_handler('authorized', self.h_authorized)

		self._clist = None
		self._creq_id = None
		self._vreq_id = None
		self._FN = None

	def auth(self, user, password):
		# Connect to server:
		# TODO: async connect with threading - connect can block server
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

		body = "".join([m for m in msg['body'].nodes if isinstance(m, basestring)])

		self.mrim.send_message(body, msg_to)

	def subscribe(self, to, xml):
		D = mrim.MRIMData( ('user', 'LPS') )
		D.data['user'] = to
		m = mrim.MRIMPacket(msg = mrim.MRIM_CS_AUTHORIZE)
		m.data = D.encode()

		self.mrim.send_msg(m)

	def unsubscribe(self, to, xml):
		# TODO: do something...
		pass

	def pollRegister(self, poll):
		self.mrim.pollRegister(poll)

	def idle(self):
		self.mrim.ping()

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
		# Message from MRIM:
		m = XMLNode('message', { "from": msg.address, 'type': 'chat', 'xmlns': 'jabber:client' })
		m.nodes.append(XMLNode('body'))
		m['body'].nodes.append(msg.msg)

		self.server.send(m.toString(pack = True))

		msg.submit()

	def h_login_success(self):
		self.server.authSuccess()

	def h_login_reject(self, reason):
		self.server.authReject()

	def h_user_info(self, info):
		self._FN = info['MRIM.NICKNAME'].decode(mrim.MRIM_ENCODING)
		if self._vreq_id:
			self._send_vcard()

	def h_connection_closed(self):
		self.server.close()

	def _send_vcard(self):
		d = self.server.from_.split('.')[0]
		self.server.sendVCard(self._vreq_id, {'FN': self._FN, "URL": "http://http://r.mail.ru/cln3587/my.mail.ru/%s/%s/" % (d, self.server.user)})

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

	def h_authorization_request(self, msg):
		self.server.sendSubscriptionRequest(msg.address)

	def h_authorized(self, user):
		self.server.sendSubscribe(user)

if __name__ == '__main__':
	J = eserver.EventServer(('localhost', 5222), JabberServer, [MRIMGW])
	J.poll_timeout = 1000
	try:
		J.start()
	except:
		print_exc()
		J.stop()

