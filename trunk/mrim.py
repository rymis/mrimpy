#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
	Mail.ru agent protocol implementation with Python
"""

LIB_VERSION = '0.01'
__version__ = LIB_VERSION

MRIM_ENCODING='cp1251'

import socket
import struct
import threading
import select
import time
import base64
import zlib
import email
from traceback import print_exc

#try:
#	import syslog
#	syslog.openlog('MRIM')
#
#	log = syslog.syslog
#except:
def log(msg):
	print "[MRIM] %s" % msg

class MRIMError(Exception):
	pass

PROTO_VERSION_MAJOR = 1
PROTO_VERSION_MINOR = 7
PROTO_VERSION = (PROTO_VERSION_MAJOR << 16) | PROTO_VERSION_MINOR
CS_MAGIC = 0xDEADBEEF		# Клиентский Magic ( C <-> S )

STATUS_OFFLINE =	0x00000000
STATUS_ONLINE =		0x00000001
STATUS_AWAY =		0x00000002
STATUS_UNDETERMINATED =	0x00000003
STATUS_FLAG_INVISIBLE =	0x80000000

def PROTO_MAJOR(p):
	return (((p)&0xFFFF0000)>>16)

def PROTO_MINOR(p):
	return ((p)&0x0000FFFF)

class MRIMData(object):
	"""
	MRIMData ojects can work as any of mrim data types using format. Format is sequence (name, type, name, type, ...).
For example:
(
	'from', 'LPS',
	'msg_id', 'UL'
) is data of cs_message_recv. You can use simple form:
	msg.data['from'] = 'nobody@mail.ru' and et.c. for manipulating this parameters.
	"""
	def __init__(self, fmt = None):
		self.fmt = []
		self.data = {}

		if fmt:
			self.set_format(fmt)

	def set_format(self, fmt):
		" set format for data "
		self.fmt = list(fmt)[:] # Copy

		self.data = {}
		par = True
		for i in fmt:
			if par:
				self.data[i] = None
			par = not par

	def encode(self):
		" encode data into string "
		name = None
		type = None
		par = True

		str = ''

		for f in self.fmt:
			if par:
				name = f
			else:
				type = f

				str += self.encode_type(type, self.data[name])
			par = not par

		return str

	def decode(self, data):
		" decode data from string "
		name = None
		type = None
		par = True

		for f in self.fmt:
			if par:
				name = f
			else:
				type = f
				data, self.data[name] = self.decode_type(type, data)

			par = not par

	def encode_type(self, type, val):
		" encode value val of type type "
		if type == 'UL':
			return struct.pack('<l', int(val))
		elif type == 'LPS':
			return struct.pack('<l%ds'%len(val), len(val), val)
		elif type == 'UIDL':
			v = base64.b64decode(val)
			if len(v) != 8:
				raise MRIMError, "Invalid parameter passed to UIDL"
			return v
		else:
			raise MRIMError, "Unknon type: %s" % type

	def decode_type(self, type, data):
		" decode value of type from data "
		if type == 'UL':
			return (data[4:], struct.unpack('<l', data[:4])[0])
		elif type == 'LPS':
			len = struct.unpack('<l', data[:4])[0]
			return (data[len+4:], data[4:len+4])
		elif type == 'UIDL':
			val = base64.b64encode(data[:8])
			return (data[8:], val)
		else:
			raise MRIMError, "Unknon type: %s" % type

MRIM_CS_HELLO = 0x1001
MRIM_CS_HELLO_ACK = 0x1002
MRIM_LOGIN2 = 0x1038  # C -> S
MRIM_LOGIN_ACK = 0x1004
MRIM_LOGIN_REJ = 0x1005
MRIM_CS_PING = 0x1006
MRIM_CS_MESSAGE = 0x1008  # C -> S



MESSAGE_FLAG_OFFLINE =		0x00000001
MESSAGE_FLAG_NORECV =		0x00000004
MESSAGE_FLAG_AUTHORIZE =		0x00000008 	# X-MRIM-Flags: 00000008
MESSAGE_FLAG_SYSTEM =		0x00000040
MESSAGE_FLAG_RTF =		0x00000080
MESSAGE_FLAG_CONTACT =		0x00000200
MESSAGE_FLAG_NOTIFY =		0x00000400
MESSAGE_FLAG_MULTICAST =		0x00001000
MAX_MULTICAST_RECIPIENTS = 50
MESSAGE_USERFLAGS_MASK =	0x000036A8	# Flags that user is allowed to set himself

mrim_types = [
	( MRIM_CS_HELLO,
		(
		)
	),
	( MRIM_CS_HELLO_ACK,
		(
			'ping_period', 'UL'
		)
	),
	( MRIM_LOGIN2,
		(
			'login', 'LPS',
			'password', 'LPS',
			'status', 'UL',
			'description', 'LPS'
		)
	),
	( MRIM_LOGIN_ACK,
		(
		)
	),
	( MRIM_LOGIN_REJ,
		(
			'reason', 'LPS'
		)
	),
	( MRIM_CS_PING,
		(
		)
	),
	( MRIM_CS_MESSAGE,
		(
			'flags', 'UL',
			'to', 'LPS',
			'message', 'LPS',
			'rtf', 'LPS'
		)
	),
]

def get_mrim_data(type):
	" create MRIMData object of type "
	for t in mrim_types:
		if t[0] == type:
			return MRIMData(t[1])

	return None

class mrim_packet(object):
	" Low-level MRIM message "

	def __init__(self, magic = CS_MAGIC, proto = PROTO_VERSION, msg = None, fromaddr = 0, fromport = 0, data = None):
		self.magic = magic
		self.proto = proto
		self.seq = -1
		self.msg = msg

		self.data = data
		self.fromaddr = fromaddr
		self.fromport = fromport
		self.reserved = '\0'*16

	def __reverse(self, i):
		" reverse i bytes "
		return (((i&0xFF) << 24) | ((i&0xFF00) << 8) | ((i&0xFF0000)>>8) | ((i&0xFF000000)>>24))

	def encode(self):
		" encode data to send it over network: "
		if len(self.reserved) == 16:
			res = self.reserved
		else:
			res = '\0'*16

		if not self.data:
			d = ''
		else:
			d = self.data
		return struct.pack('<7l16s%ds'%len(d), self.magic, self.proto, self.seq, self.msg, len(d), self.__reverse(self.fromaddr), self.__reverse(self.fromport), res, d)

	def send(self, sock):
		" send packet over network. addr and port will be calculated at this point "
		self.fromaddr, self.fromport = sock.getsockname()
		self.fromaddr = struct.unpack('>l', socket.inet_aton(self.fromaddr))[0]
		str = self.encode()

		while len(str) > 0:
			l = sock.send(str)
			if l < 0:
				raise MRIMError, "Network problems"
			str = str[l:]

	def recv(self, sock):
		" receive data header from socket "
		ln = struct.calcsize('<7l16s')

		# read len bytes:
		str = ''
		while len(str) < ln:
			d = sock.recv(ln - len(str))
			if len(d) == 0:
				raise MRIMError, "Connection closed"
			str += d

		self.decode(str)

		if self.dlen:
			# read data from socket:
			str = ''
			while len(str) < self.dlen:
				d = sock.recv(self.dlen - len(str))
				if len(d) == 0:
					raise MRIMError, "Connection closed"
				str += d

			self.data = str
		else:
			self.data = ''

	def decode(self, str):
		" decode header "
		self.magic, self.proto, self.seq, self.msg, self.dlen, fromaddr, fromport, res = struct.unpack('<7l16s', str)
		self.fromaddr = socket.ntohl(fromaddr)
		self.fromport = socket.ntohl(fromport)
		self.data = None

	def decode_data(self):
		" Get MRIMData from decoded packet "
		for t in mrim_types:
			if t[0] == self.msg:
				d = MRIMData(t[1])
				d.decode(self.data)
				return d
		return None # Unknown message type

	def __repr__(self):
		return "MRIM Message { type: %x, seq: %d }" % (self.msg, self.seq)

	
MRIM_CS_MESSAGE_ACK =		0x1009  # S -> C
	# UL msg_id
	# UL flags
	# LPS from
	# LPS message
	# LPS rtf-formatted message (>=1.1)
	
MRIM_CS_MESSAGE_RECV =	0x1011	# C -> S
	# LPS from
	# UL msg_id

MRIM_CS_MESSAGE_STATUS =	0x1012	# S -> C
	# UL status
MESSAGE_DELIVERED =		0x0000	# Message delivered directly to user
MESSAGE_REJECTED_NOUSER =		0x8001  # Message rejected - no such user
MESSAGE_REJECTED_INTERR =		0x8003	# Internal server error
MESSAGE_REJECTED_LIMIT_EXCEEDED =	0x8004	# Offline messages limit exceeded
MESSAGE_REJECTED_TOO_LARGE =	0x8005	# Message is too large
MESSAGE_REJECTED_DENY_OFFMSG =	0x8006	# User does not accept offline messages

MRIM_CS_USER_STATUS =	0x100F	# S -> C
	# UL status
	# LPS user
	
MRIM_CS_LOGOUT =			0x1013	# S -> C
	# UL reason
LOGOUT_NO_RELOGIN_FLAG =	0x0010		# Logout due to double login
	
MRIM_CS_CONNECTION_PARAMS =	0x1014	# S -> C
	# mrim_connection_params_t

MRIM_CS_USER_INFO =			0x1015	# S -> C
	# (LPS key, LPS value)* X
	
			
MRIM_CS_ADD_CONTACT =			0x1019	# C -> S
	# UL flags (group(2) or usual(0) 
	# UL group id (unused if contact is group)
	# LPS contact
	# LPS name
	# LPS unused
CONTACT_FLAG_REMOVED =	0x00000001
CONTACT_FLAG_GROUP =	0x00000002
CONTACT_FLAG_INVISIBLE =	0x00000004
CONTACT_FLAG_VISIBLE =	0x00000008
CONTACT_FLAG_IGNORE =	0x00000010
CONTACT_FLAG_SHADOW =	0x00000020
	
MRIM_CS_ADD_CONTACT_ACK	 =		0x101A	# S -> C
	# UL status
	# UL contact_id or (u_long)-1 if status is not OK
	
CONTACT_OPER_SUCCESS =		0x0000
CONTACT_OPER_ERROR =		0x0001
CONTACT_OPER_INTERR =		0x0002
CONTACT_OPER_NO_SUCH_USER =	0x0003
CONTACT_OPER_INVALID_INFO =	0x0004
CONTACT_OPER_USER_EXISTS =	0x0005
CONTACT_OPER_GROUP_LIMIT =	0x6

MRIM_CS_MODIFY_CONTACT =			0x101B	# C -> S
	# UL id
	# UL flags - same as for MRIM_CS_ADD_CONTACT
	# UL group id (unused if contact is group)
	# LPS contact
	# LPS name
	# LPS unused
	
MRIM_CS_MODIFY_CONTACT_ACK =		0x101C	# S -> C
	# UL status, same as for MRIM_CS_ADD_CONTACT_ACK

MRIM_CS_OFFLINE_MESSAGE_ACK =		0x101D	# S -> C
	# UIDL
	# LPS offline message

MRIM_CS_DELETE_OFFLINE_MESSAGE =		0x101E	# C -> S
	# UIDL

	
MRIM_CS_AUTHORIZE =			0x1020	# C -> S
	# LPS user
	
MRIM_CS_AUTHORIZE_ACK =			0x1021	# S -> C
	# LPS user

MRIM_CS_CHANGE_STATUS =			0x1022	# C -> S
	# UL new status


MRIM_CS_GET_MPOP_SESSION =		0x1024	# C -> S
	
	
MRIM_CS_MPOP_SESSION =			0x1025	# S -> C
	#define MRIM_GET_SESSION_FAIL		0
	#define MRIM_GET_SESSION_SUCCESS	1
	#UL status 
	# LPS mpop session


MRIM_CS_WP_REQUEST =			0x1029 #C->S
#DWORD field, LPS value
PARAMS_NUMBER_LIMIT =			50
PARAM_VALUE_LENGTH_LIMIT =		64

#if last symbol in value eq '*' it will be replaced by LIKE '%' 
# params define
# must be  in consecutive order (0..N) to quick check in check_anketa_info_request
(
  MRIM_CS_WP_REQUEST_PARAM_USER,
  MRIM_CS_WP_REQUEST_PARAM_DOMAIN,
  MRIM_CS_WP_REQUEST_PARAM_NICKNAME,
  MRIM_CS_WP_REQUEST_PARAM_FIRSTNAME,
  MRIM_CS_WP_REQUEST_PARAM_LASTNAME,
  MRIM_CS_WP_REQUEST_PARAM_SEX,
  MRIM_CS_WP_REQUEST_PARAM_BIRTHDAY,
  MRIM_CS_WP_REQUEST_PARAM_DATE1,
  MRIM_CS_WP_REQUEST_PARAM_DATE2,
  #!!!!!!!!!!!!!!!!!!!online request param must be at end of request!!!!!!!!!!!!!!!
  MRIM_CS_WP_REQUEST_PARAM_ONLINE,
  MRIM_CS_WP_REQUEST_PARAM_STATUS, # we do not used it, yet
  MRIM_CS_WP_REQUEST_PARAM_CITY_ID,
  MRIM_CS_WP_REQUEST_PARAM_ZODIAC,
  MRIM_CS_WP_REQUEST_PARAM_BIRTHDAY_MONTH,
  MRIM_CS_WP_REQUEST_PARAM_BIRTHDAY_DAY,
  MRIM_CS_WP_REQUEST_PARAM_COUNTRY_ID,
  MRIM_CS_WP_REQUEST_PARAM_MAX
) = range(17)

MRIM_CS_ANKETA_INFO =			0x1028 #S->C
#DWORD status 
MRIM_ANKETA_INFO_STATUS_OK =		1
MRIM_ANKETA_INFO_STATUS_NOUSER =		0
MRIM_ANKETA_INFO_STATUS_DBERR =		2
MRIM_ANKETA_INFO_STATUS_RATELIMERR =	3
#DWORD fields_num				
#DWORD max_rows
#DWORD server_time sec since 1970 (unixtime)
# fields set 				#%fields_num == 0
#values set 				#%fields_num == 0
#LPS value (numbers too)

	
MRIM_CS_MAILBOX_STATUS =			0x1033	
#DWORD new messages in mailbox


MRIM_CS_CONTACT_LIST2 =		0x1037 #S->C
# UL status
GET_CONTACTS_OK =			0x0000
GET_CONTACTS_ERROR =		0x0001
GET_CONTACTS_INTERR =		0x0002
#DWORD status  - if ...OK than this staff:
#DWORD groups number
#mask symbols table:
#'s' - lps
#'u' - unsigned long
#'z' - zero terminated string 
#LPS groups fields mask 
#LPS contacts fields mask 
#group fields
#contacts fields
#groups mask 'us' == flags, name
#contact mask 'uussuu' flags, flags, internal flags, status
	#define CONTACT_INTFLAG_NOT_AUTHORIZED	0x0001

###############################################################################

class MRIMContact(object):
	def __init__(self):
		self.address = u""
		self.nick = u""
		self.group = -1
		self.group_name = u""
		self.server_flags = 0
		self.status = STATUS_OFFLINE

class MRIMMessage(object):
	def __init__(self, msg = u"", xml_msg = None, rtf_msg = None, flags = 0, mrim = None, address = None):
		" Create new message "
		self.msg = msg
		self.xml_msg = xml_msg
		self.rtf_msg = rtf_msg
		self.flags = flags
		self.mrim = None
		self.uidl = None
		self.address = address

	def encode(self):
		" Encode message for sending "
		# TODO: RTF part
		D = MRIMData( ('flags', 'UL', 'to', 'LPS', 'txt', 'LPS', 'rtf', 'TXT') )
		D.data['flags'] = self.flags
		D.data['to'] = self.address
		if isinstance(self.msg, unicode):
			self.msg = self.msg.encode(MRIM_ENCODING, 'replace')
		D.data['txt'] = self.msg
		D.data['rtf'] = ' '

		return D.encode()

	def decode(self, data):
		" Decode online message "
		pass

	def decode_offline(self, rfc822):
		" Decode MRIM offline message "
		D = MRIMData( ('uidl', 'UIDL', 'message', 'LPS') )
		D.decode(rfc822)
		M = email.message_from_string(D.data['message'])

		# Process message:
		self.address = M['from']
		text_part = None
		rtf_part = None
		for part in M.walk():
			if part.get_content_maintype() == 'text':
				if not text_part:
					text_part = part.get_payload(decode = True)
				else:
					rtf_part = part.get_payload(decode = True)

		self.msg = ""
		for s in text_part.split('\n'):
			if not s.startswith('--'):
				self.msg += "%s\n" % s
		self.msg = self.msg.decode(MRIM_ENCODING, 'replace')
		try:
			if rtf_part:
				self.rtf_msg = zlib.decompress(base64.b64decode(rtf_part))
		except:
			self.rtf_msg = None

		self.uidl = D.data['uidl']

		self._make_xml()

	def submit(self):
		" If this is offline message - then delete it, else sens MSG_RECV to server "
		pass

	def status(self):
		" Status of sent message "
		return 0

	def is_authorization(self):
		" Is message authorization request "
		return ((self.flags & MESSAGE_FLAG_AUTHORIZE) != 0)

	def is_offline(self):
		" Is message delivered offline "
		return ((self.flags & MESSAGE_FLAG_OFFLINE) != 0)

	def set_flag(self, flag):
		" Set flags to message "
		self.flags |= flag

	def _make_xml(self):
		if not self.rtf_msg:
			self.xml_msg = self.msg
		else:
			# TODO: process RTF
			msg = self.rtf.replace('{', '').replace('}', '')

class MRIMPlugin(object):
	def message_received(self, message):
		" Callback of received message "
		pass
	
	def message_sent(self, message):
		" Called, when message sent. (Don't work at this time) "
		pass

	def register(self, mrim):
		" This method will be call'ed for register this plugin "
		self.mrim = mrim

	def is_my_message(self, mrim_type):
		" Return is message supported by plugin "
		if hasattr(self, 'MESSAGE'):
			return mrim_type == self.MESSAGE
		return False


class MailRuAgent(object):
	" main class for protocol "

	def __init__(self, no_load_plugins = False):
		self.sock = None
		self.ping_period = 60
		self.seq = 0
		self.plugins = {}
		self.methods = {}
		self.actions = { "message_received": [], "contact_list_received": [], "user_info": [], "offline_message": [] }
		self._msg_cache = []

		if not no_load_plugins:
			import mrim_plugins
			self.load_plugins(mrim_plugins.PLUGINS_ALL)

	def load_plugins(self, plugins):
		" Load all plugins from plugins list "
		for p in plugins:
			plug = self.plugins[p.__name__] = p()
			plug.register(self)

	def call_action(self, name, args):
		" Call action name with args: "
		log("Action <%s>" % name)
		if self.actions.has_key(name):
			for h in self.actions[name]:
				try:
					h(*args)
				except:
					log("Error: Action handler failed")
					print_exc()

	def add_handler(self, name, func, method = "append"):
		" Add action handler "
		if not self.actions.has_key(name):
			self.actions[name] = []

		if method == 'append':
			self.actions[name].append(func)
		elif method == 'prepend':
			self.actions[name].insert(0, func)
		else:
			raise MRIMError, "Unknown method: %s" % method

	def add_method(self, name, func):
		if self.methods.has_key(name):
			raise MRIMError, "Duplicate method definition: %s" % name
		self.methods[name] = func

	def __getattr__(self, name):
		return self.methods[name]

	def connect(self, user, password, server = 'mrim.mail.ru', port = 2042, status = STATUS_ONLINE):
		" Connect to mail.ru server "
		# Get IP:Port from mail.ru server:
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
		sock.connect((server, port))

		str = ''
		a = 'a'
		while len(a) > 0:
			a = sock.recv(256)
			str += a
		sock.close()

		self._addr, self._port = str.split(':')

		log('Connecting to %s:%s' %(self._addr, self._port))
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
		self.sock.connect((self._addr, int(self._port)))

		# Send hello:
		log('Sending hello...')
		msg = mrim_packet(msg = MRIM_CS_HELLO)
		msg.seq = self.seq
		msg.send(self.sock)

		# And receive ack:
		log('Receiving ACK...')
		msg = mrim_packet()
		msg.recv(self.sock)

		if msg.msg != MRIM_CS_HELLO_ACK:
			log("Error: not valid message from server")
			raise MRIMError, 'Invalid server answere'
		self.ping_period = msg.decode_data().data['ping_period']
		log('PING period is set to %d' % self.ping_period)

		self.seq += 1

		# Send login and password:
		l = get_mrim_data(MRIM_LOGIN2)
		l.data['login'] = user
		l.data['password'] = password
		l.data['status'] = status
		l.data['description'] = 'MRIM Python library v%s. <rymis@mail.ru>' % LIB_VERSION

		log('Sending login...')
		msg = mrim_packet(msg = MRIM_LOGIN2)
		msg.seq = self.seq
		msg.data = l.encode()
		msg.send(self.sock)

		# And receive answere:
		log('Receiving answere...')
		msg = mrim_packet()
		msg.recv(self.sock)

		if msg.msg == MRIM_LOGIN_ACK:
			# Ok.
			log("Login OK...")
			pass
		elif msg.msg == MRIM_LOGIN_REJ:
			raise MRIMError, "Login rejected: %s" % msg.decode_data().data['reason']
		else:
			raise MRIMError, "Unknown protocol message from server"

		self.last_ping = time.time()

	def is_connected(self):
		return self.sock != None

	def close(self):
		" Logout and close connection "
		if self.sock:
			self.sock.close()
			self.sock = None

	def send(self, msg):
		msg.send(self.sock)

	def idle(self):
		" this function will try to read server message, and if present call action handler. Also if need ping processed. "
		if not self.sock:
			return

		t = time.time()
		if abs(t - self.last_ping) > self.ping_period:
			self._ping()
			self.last_ping = time.time()

		(r, w, x) = select.select([self.sock], [], [], 0)
		if r == []:
			return None

		msg = mrim_packet()
		msg.recv(self.sock)

		log("New message from server: %s"% repr(msg))
		# TODO: call action handlers

		for pn in self.plugins:
			p = self.plugins[pn]
			if p.is_my_message(msg.msg):
				log("Plugin %s: processing message..." % pn)
				p.message_received(msg)

	def _ping(self):
		log("PING")
		msg = mrim_packet(msg = MRIM_CS_PING)
		seq = self.seq = self.seq + 1
		seq -= 1
		msg.seq = seq
		msg.send(self.sock)

	def change_status(self, status):
		" Change user status "
		log("Change status to %d" % status)
		msg = mrim_packet(msg = MRIM_CS_CHANGE_STATUS)
		seq = self.seq = self.seq + 1
		seq -= 1
		msg.seq = seq
		l = get_mrim_data(MRIM_CS_CHANGE_STATUS)
		l['status'] = status
		msg.data = l.encode()

		msg.send(self.sock)

		if status == STATUS_OFFLINE:
			self.close()

	def send_message(self, msg, addr = None):
		if not isinstance(msg, MRIMMessage):
			txt = msg
			if not addr:
				raise MRIMError, "Not enought params in send_message "
			msg = MRIMMessage(msg = txt, flags = MESSAGE_FLAG_NORECV, address = addr)

		M = mrim_packet(msg = MRIM_CS_MESSAGE)
		M.seq = self.seq
		self.seq += 1
		M.data = msg.encode()

		# Save this message to cache:
		if not (msg.flags & MESSAGE_FLAG_NORECV):
			self._msg_cache.append( (M.seq, msg) )
		msg.send(self.sock)

		return M.seq

if __name__ == '__main__':
	d = MRIMData(('name', 'LPS', 'value', 'UL'))
	d.data['name'] = 'yo'
	d.data['value'] = 123
	s = d.encode()
	print s
	d.decode(s)
	print d.data
