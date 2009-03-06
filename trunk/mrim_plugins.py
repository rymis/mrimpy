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
		self.mrim.call_action('user_info', (msg, ui))

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
		for i in range(gcnt):
			cl.append([])

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

			if len(cl) > contact['group']: 
				cl[contact['group']].append(contact)

		self.mrim.call_action('contact_list', (groups, cl))

class OfflineMessage(MRIMPlugin):
	MESSAGE = MRIM_CS_OFFLINE_MESSAGE_ACK

	def message_received(self, msg):
		" process offline message "
		D = MRIMData( ('uidl', 'UIDL', 'message', 'LPS') )
		D.decode(msg.data)
		M = email.message_from_string(D.data['message'])

		M['X-MRIM-UIDL'] = D.data['uidl']

		self.mrim.call_action('offline_message', [M])

	def register(self, mrim):
		self.mrim = mrim
		mrim.add_method('offline_message_del', self.offline_message_del)

	def offline_message_del(self, uidl):
		if not isinstance(uidl, str):
			uidl = uidl['X-MRIM-UIDL']

		log("Removing message with UIDL[%s]" % uidl)
		# TODO remove message

class RTFFormat(MRIMPlugin):
	def register(self, mrim):
		self.mrim = mrim
		mrim.add_method('rtf2text', self.rtf2text)

	def rtf_decode(self, rtf):
		msg = zlib.decompress(base64.b64decode(rtf))
		D = MRIMData( ('lpscnt', 'UL', 'rtf', 'LPS', 'background', 'LPS') )
		d, rtf_f = D.decode(msg)

		return rtf_f['rtf']

	def rtf2text(self, rtf):
		return rtf_decode(rtf)

PLUGINS_ALL = [ UserInfo(), ContactList2(), OfflineMessage(), RTFFormat() ]

