# -*- coding: utf-8 -*-

"""
Plugins for mrim.py.
"""

from mrim import *
import email
import zlib
import base64

class UserInfo(MRIMPlugin):
	" MRIM_CS_USER_INFO processor "
	MESSAGE = MRIM_CS_USER_INFO

	def message_received(self, msg):
		ui = self._user_info_decode(msg.data)
		self.mrim.call_action('user_info', [ui])

	def _user_info_decode(self, d):
		ui = {}
		while True:
			sl = struct.unpack('<l', d[:4])[0]
			key = d[4:sl + 4]
			d = d[4+sl:]

			sl = struct.unpack('<l', d[:4])[0]
			val = d[4:sl + 4]
			d = d[4+sl:]

			ui[key] = val

			if len(d) < 4:
				break

		return ui

class ContactList2(MRIMPlugin):
	MESSAGE = MRIM_CS_CONTACT_LIST2

	def message_received(self, msg):
		d = msg.data

		D = MRIMData()
		status = struct.unpack('<l', d[:4])[0]
		if status != GET_CONTACTS_OK:
			return # Nothing to do
		d = d[4:]
		gcnt = struct.unpack('<l', d[:4])[0]
		d = d[4:]
		d, gfmt_s = D.decode_type('LPS', d)
		d, cfmt_s = D.decode_type('LPS', d)

		gfmt = []
		cfmt = []
		for f in gfmt_s:
			if f == 's':
				gfmt.append('LPS')
			elif f == 'u':
				gfmt.append('UL')
			else:
				raise MRIMError, "Unknown format from server"
		for f in cfmt_s:
			if f == 's':
				cfmt.append('LPS')
			elif f == 'u':
				cfmt.append('UL')
			else:
				raise MRIMError, "Unknown format from server"

		groups = []
		for i in range(gcnt):
			g = []
			for f in gfmt:
				d, val = D.decode_type(f, d)
				g.append(val)

			if len(g) < 2:
				raise MRIMError, "Invalid group format"

			groups.append({'flags': g[0], 'name': g[1].decode(MRIM_ENCODING)})

		cl = []
		while len(d) > 0:
			c = []
			for f in cfmt:
				d, val = D.decode_type(f, d)
				c.append(val)

			if len(c) < 6:
				raise MRIMError, "Unknown contact format"

			contact = {}
			contact['flags'] = c[0]
			contact['group'] = c[1]
			contact['address'] = c[2]
			contact['nick'] = c[3].decode(MRIM_ENCODING)
			contact['server_flags'] = c[4]
			contact['status'] = c[5]

			cl.append(contact)

		self.mrim.call_action('contact_list', (groups, cl))

class OfflineMessage(MRIMPlugin):
	MESSAGE = MRIM_CS_OFFLINE_MESSAGE_ACK

	def message_received(self, msg):
		" process offline message "
		log("Offline message...")
		M = MRIMMessage()
		M.mrim = self.mrim
		M.decode_offline(msg.data)

		self.mrim.process_message(M)

class MessageACK(MRIMPlugin):
	MESSAGE = MRIM_CS_MESSAGE_ACK

	def message_received(self, msg):
		M = MRIMMessage()
		M.mrim = self.mrim
		M.decode(msg.data)

		self.mrim.process_message(M)
	
class MessageStatus(MRIMPlugin):
	MESSAGE = MRIM_CS_MESSAGE_STATUS

	def message_received(self, msg):
		D = MRIMData( ('status', 'UL' ) )
		D.decode(msg.data)

		self.mrim.call_action( "message_status", [D.data['status']])

class ConnectionParams(MRIMPlugin):
	MESSAGE = MRIM_CS_CONNECTION_PARAMS

	def message_received(self, msg):
		D = MRIMData( ('ping_period', 'UL') )
		D.decode(msg.data)

		self.mrim.ping_period = D.data['ping_period']

class UserStatus(MRIMPlugin):
	MESSAGE = MRIM_CS_USER_STATUS

	def message_received(self, msg):
		D = MRIMData( ('status', 'UL', 'user', 'LPS') )
		D.decode(msg.data)

		self.mrim.call_action( 'user_status', (D.data['user'], D.data['status']))

class HelloACK(MRIMPlugin):
	MESSAGE = MRIM_CS_HELLO_ACK

	def message_received(self, msg):
		D = MRIMData( ('ping_period', 'UL') )
		D.decode(msg.data)
		self.mrim.ping_period = D.data['ping_period']
		log('PING period is set to %d' % self.mrim.ping_period)

		self.mrim.state = SESSION_OPENED

		self.mrim.call_action('hello_ack', [])

class LoginACK(MRIMPlugin):
	MESSAGE = MRIM_LOGIN_ACK

	def message_received(self, msg):
		log("Login Ok.")
		self.mrim.state = LOGGED_IN
		self.mrim.call_action("login_success", [])


class LoginReject(MRIMPlugin):
	MESSAGE = MRIM_LOGIN_REJ

	def message_received(self, msg):
		log("Login Ok.")
		D = MRIMData( ('reason', 'LPS') )
		D.decode(msg.data)
		self.mrim.call_action("login_reject", [D.data['reason']])
		self.mrim.close()

class Authorized(MRIMPlugin):
	MESSAGE = MRIM_CS_AUTHORIZE_ACK

	def message_received(self, msg):
		D = MRIMData( ('user', 'LPS') )
		D.decode(msg.data)
		user = D.data['user']
		log("Authorization from user: %s" % user)

		self.mrim.call_action('authorized', [user])


PLUGINS_ALL = [ UserInfo, ContactList2, OfflineMessage, MessageStatus,
		MessageACK, ConnectionParams, UserStatus, HelloACK,
		LoginACK, LoginReject, Authorized ]

