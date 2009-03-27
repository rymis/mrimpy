#!/usr/bin/env python
# -*- coding: utf-8 -*-

__licence__ = """
Copyright (C) 2009 Mikhail Ryzhov <rymiser@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>
"""

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
		self.mrim.add_handler('search_user_error', self.h_search_user_error)
		self.mrim.add_handler('contact_info', self.h_contact_info)

		self._clist = None
		self._creq_id = None
		self._vreq_id = None
		self._FN = None
		self._vCard_Requests = []

	def auth(self, user, password):
		# Connect to server:
		# TODO: async connect with threading - connect can block server
		self.mrim.connect()
		self._auth = (user, password)

	def vCardRequest(self, id, to):
		if not to or to.split('/')[0] == self.mrim_user:
			self._vreq_id = id
			if self._FN:
				self._send_vcard()
		else:
			seq = self.mrim.request_user_info(to)
			self._vCard_Requests.append( (id, seq, to) )

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

	def h_search_user_error(self, seq, status):
		print "Search user error."
		for q in self._vCard_Requests:
			if q[1] == seq:
				id = q[0]
				user = q[2]
				self._vCard_Requests.remove(q)
				r = XMLNode('iq', { 'type': 'error', 'to': self.server.resource, 'from': user, 'id': id})
				r.nodes.append(XMLNode('vCard'))
				r.nodes.append(XMLNode('error'))

				if status == mrim.MRIM_ANKETA_INFO_STATUS_NOUSER:
					r['error'].nodes.append('user-not-found')
					r['error'].nodes.append(XMLNode('text', { 'xmlns': 'urn:ietf:params:xml:ns:xmpp-stanzas' }))
					r['error']['text'].nodes.append("User not found")
				elif status == mrim.MRIM_ANKETA_INFO_STATUS_RATELIMERR:
					r['error'].nodes.append('too-much-requests')
					r['error'].nodes.append(XMLNode('text', { 'xmlns': 'urn:ietf:params:xml:ns:xmpp-stanzas' }))
					r['error']['text'].nodes.append("Too much requests")
				else:
					r['error'].nodes.append('internal-server-error')

				self.server.send(r.toString(pack = True))
				return

	def h_contact_info(self, ui, seq):
		for q in self._vCard_Requests:
			if q[1] == seq:
				id = q[0]
				user = q[2]
				self._vCard_Requests.remove(q)

				try:
					email, domain = user.split('@')
					l = domain.rfind('.')
					if l > 0:
						domain = domain[:l]
					email = email.decode('utf-8', 'replace')
					domain = domain.decode('utf-8', 'replace')
				except:
					email = u""
					domain = u""
				vc = {}
				desc = u"""
Мой Мир: http://http://r.mail.ru/cln3587/my.mail.ru/%(domain)s/%(email_name)s/
Фото: http://r.mail.ru/cln3565/foto.mail.ru/%(domain)s/%(email_name)s/
Видео: http://r.mail.ru/cln3567/video.mail.ru/%(domain)s/%(email_name)s/
Блоги: http://r.mail.ru/cln3566/blogs.mail.ru/%(domain)s/%(email_name)s/
""" % {'domain': domain, 'email_name': email}
				for a in ui:
					if a.lower() == 'birthday':
						vc['BDAY'] = ui[a].decode(mrim.MRIM_ENCODING, 'replace')
					elif a.lower() == 'nickname':
						vc['NICKNAME'] = ui[a].decode(mrim.MRIM_ENCODING, 'replace')
					elif a.lower() == 'location':
						desc += u"Расположение: %s\n" % ui[a].decode(mrim.MRIM_ENCODING, 'replace')
					elif a.lower() == 'phone':
						x = XMLNode('NUMBER')
						x.nodes.append(ui[a].decode(mrim.MRIM_ENCODING, 'replace'))
						vc['TEL'] = x

				if len(email) > 0:
					try:
						tp, dt = mrim.load_avatar(email, domain)
						xd = XMLNode('BINVAL')
						xd.nodes.append(base64.b64encode(dt))
						xt = XMLNode('TYPE')
						xt.nodes.append(tp)
						vc['PHOTO'] = [xt, xd]
					except:
						print_exc()
						pass

				vc['DESC'] = desc

				self.server.sendVCard(id, vc, user)

				return

if __name__ == '__main__':
	J = eserver.EventServer(('localhost', 5222), JabberServer, [MRIMGW])
	J.poll_timeout = 1000
	try:
		J.start()
	except:
		print_exc()
		J.stop()

