#!/usr/bin/env python

# Main module of Jabber2MRIM gateway.

import eserver
import xmlstream
from xmlstream import XMLNode
import random
import xmpp

from mrim import MRIMPacket, MRIMData
import mrim

import base64
from traceback import print_exc

PLUGINS = xmpp.PLUGINS
class ProtocolProxy(object):
	" Mapping Jabber packets to another protocol "

	def __init__(self, jclient):
		self.xmpp = jclient

	" Callbacks: "
	def auth(self, user, password):
		" Authenticate user. Result must be sent by calling authReject or authSuccess methods "
		pass

	" Helper methods: "

class Jabber2MRIM(eserver.Protocol):
	def __init__(self, sock, server, Proxy):
		super(Jabber2MRIM, self).__init__(sock, server)

		self.xml = xmlstream.XMLInputStream()
		self.xml.h_start.append(self.startStream)
		self.xml.h_stanza.append(self.xmlReceive)
		self.xml.h_end.append(self.endStream)

		self.id = str(random.randint(100000000, 999999999))
		self.from_ = None

		self.h_xmpp = { "auth": [self.xmppAuth], "iq": [self.xmppIQ] }

		self.proxy = Proxy()

		self.iqs = {}
		for pclass in PLUGINS:
			p = pclass()
			self.iqs[p.IQTYPE] = p
		self.user = None
		self.resource = None

	def startStream(self, ns, attrs):
		print "START STREAM"
		self.from_ = attrs['to']
		self.namespace = ns

		node = XMLNode("%s:stream" % self.namespace, {
			"id": str(self.id),
			"version": "1.0",
			"xmlns": "jabber:client",
			"xmlns:stream": "http://etherx.jabber.org/streams",
			"from": self.from_
		})

		if not self.user:
			fs = XMLNode("%s:features" % self.namespace)
			mechs = XMLNode("mechanisms", {"xmlns": "urn:ietf:params:xml:ns:xmpp-sasl"})
			mech = XMLNode("mechanism")
			mech.nodes.append("PLAIN")
			mechs.nodes.append(mech)
			fs.nodes.append(mechs)
			node.nodes.append(fs)
		else:
			fs = XMLNode("%s:features" % self.namespace)
			for p in self.iqs:
				f = self.iqs[p].getFeatures()
				if f:
					fs.nodes.append(f)
			node.nodes.append(fs)
		self.send(node.toString(pack = True, noclose = True))

	def endStream(self):
		if self.mrim:
			self.mrim.close()
		self.close()
		print "The End!"

	def processData(self, buf):
		try:
			self.xml.data(buf)
		except:
			print_exc()
			self.sock.close()
			self.server.removeClient(self)

	def pollRegister(self, poll):
		if self.mrim:
			if len(self.mrim.queue) > 0:
				w_f = self.mrim._write_q
			else:
				w_f = None

			poll.register(self.mrim.sock, read_f = self.mrim._read, write_f = w_f)

	def xmlReceive(self, xml):
		if self.h_xmpp.has_key(xml.name):
			for h in self.h_xmpp[xml.name]:
				if not h(xml):
					return False
		else:
			print "Unknown stanza:\n", xml
		return True

	def xmppAuth(self, xml):
		" Authorization "
		print "AUTH"
		b64 = None
		for x in xml.nodes:
			if isinstance(x, basestring):
				b64 = x

		if not b64:
			r = XMLNode(name = "reject", attrs = {"xmlns": "urn:ietf:params:xml:ns:xmpp-sasl"})
			r.nodes.append(XMLNode(name = "not-authorized"))
			self.send(t.toString())

		str = base64.b64decode(b64)
		sl = str.split('\000')
		if len(sl) < 2:
			r = XMLNode(name = "reject", attrs = {"xmlns": "urn:ietf:params:xml:ns:xmpp-sasl"})
			r.nodes.append(XMLNode(name = "not-authorized"))
			self.send(t.toString())

		name, passwd = sl[-2:]

		try:
			self.proxy.auth(name, passwd)
			self._user = name
		except:
			print_exc()
			r = XMLNode("reject", {"xmlns": "urn:ietf:params:xml:ns:xmpp-sasl"})
			r.nodes.append(XMLNode(name = "not-authorized"))
			self.sock.send(r.toString())
			self.sock.send("</%s:stream>" % self.namespace)

	def authSuccess(self):
		r = XMLNode("success", {"xmlns": "urn:ietf:params:xml:ns:xmpp-sasl"})
		self.send(r.toString())

		self.user = self._user
		self.xml.restart()

	def authReject(self):
		r = XMLNode("reject", {"xmlns": "urn:ietf:params:xml:ns:xmpp-sasl"})
		r.nodes.append(XMLNode(name = "not-authorized"))
		self.sock.send(r.toString())
		self.sock.send("</%s:stream>" % self.namespace)

	def xmppIQ(self, xml):
		if len(xml.nodes) == 0:
			# TODO: Invalid IQ
			pass
		else:
			n = xml.nodes[0]
			if self.iqs.has_key(n.name):
				self.iqs[n.name].processIQ(xml, self)
			else:
				self.iqs[''].processIQ(xml, self)

class MRIMProxy(ProtocolProxy):
	def __init__(self, jclient):
		super(MRIMProxy, self).__init__(jclient)
		self.mrim = MailRuAgent()
		self.mrim.add_handler('auth_success', self.h_auth_success)
		self.mrim.add_handler('auth_reject', self.h_auth_reject)

	def auth(self, user, passwd):
		self.mrim.connect("%s@%s" % (user, self.xmpp.from_), passwd)
		self.xmpp.authSuccess()

	def h_auth_success(self):
		self.xmpp.authSuccess()

	def h_auth_reject(self, reason):
		self.xmpp.authReject()

if __name__ == '__main__':
	S = eserver.EventServer( ('localhost', 5222), Jabber2MRIM )
	try:
		S.start()
	except:
		S.stop()

