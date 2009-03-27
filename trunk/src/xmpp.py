#!/usr/bin/env python

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

# Main module of Jabber2MRIM gateway.

import eserver
import xmlstream
from xmlstream import XMLNode
import random
import xmpp_plugins
import base64
from traceback import print_exc

class XMPPError(Exception):
	pass

PLUGINS = xmpp_plugins.PLUGINS
class ProtocolProxy(object):
	" Mapping Jabber packets to another protocol "

	def __init__(self):
		self.server = None

	" Callbacks: "
	def auth(self, user, password):
		" Authenticate user. Result must be sent by calling authReject or authSuccess methods "
		pass

	def pollRegister(self, poll):
		" Register sockets in poll "
		pass

	def vCardRequest(self, id, to):
		" Return vCard of client, using sendVCard method "
		raise XMPPError, "Not supported"

	def rosterRequest(self, id):
		" Return roster using sendRoster method "
		raise XMPPError, "Not supported"

	def presence(self, type, xml):
		" set client presence to type "
		pass

	def message(self, msg):
		" message received as XML "
		pass

	def subscribe(self, to, xml):
		" Subscribe to user status "
		raise XMPPError, "Not supported"

	def unsubscribe(self, to, xml):
		" Unsubscribe from user "
		raise XMPPError, "Not supported"

	def idle(self):
		" Idle function"
		pass

class JabberServer(eserver.Protocol):
	def __init__(self, sock, server, Proxy):
		super(JabberServer, self).__init__(sock, server)

		self.xml = xmlstream.XMLInputStream()
		self.xml.h_start.append(self.startStream)
		self.xml.h_stanza.append(self.xmlReceive)
		self.xml.h_end.append(self.endStream)

		self.id = str(random.randint(100000000, 999999999))
		self.from_ = None

		self.h_xmpp = { "auth": [self.xmppAuth], "iq": [self.xmppIQ], 'presence': [self.xmppPresence], 'message': [self.xmppMessage] }

		self.proxy = Proxy()
		self.proxy.server = self

		self.iqs = {}
		for pclass in PLUGINS:
			p = pclass()
			self.iqs[p.IQTYPE] = p
		self.user = None
		self.resource = None
		self.presence = "online"

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
		self.proxy.pollRegister(poll)

	def xmlReceive(self, xml):
		if self.h_xmpp.has_key(xml.name):
			for h in self.h_xmpp[xml.name]:
				try:
					if not h(xml):
						return False
				except:
					print_exc()
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
			self._user = name
			self.proxy.auth(name, passwd)
		except:
			print_exc()
			r = XMLNode("reject", {"xmlns": "urn:ietf:params:xml:ns:xmpp-sasl"})
			r.nodes.append(XMLNode(name = "not-authorized"))
			self.sock.send(r.toString())
			self.sock.send("</%s:stream>" % self.namespace)

	def authSuccess(self):
		" Success authorization "
		r = XMLNode("success", {"xmlns": "urn:ietf:params:xml:ns:xmpp-sasl"})
		self.send(r.toString())

		self.user = self._user
		self.xml.restart()

	def authReject(self):
		" Authorization failure "
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

	def xmppPresence(self, xml):
		if xml.attrs.has_key('type'):
			type = xml.attrs['type']
		else:
			type = 'online'

		if type == 'online' or type == 'unavailable':
			if xml['show']:
				show = xml['show'].nodes[0]
			else:
				show = 'online'
			self.proxy.presence(show, xml)
		elif type == 'subscribed':
			to = xml.attrs['to']
			self.proxy.subscribe(to, xml)
		elif type == 'unsubscribed':
			to = xml.attrs['to']
			self.proxy.unsubscribe(to, xml)

	def xmppMessage(self, xml):
		self.proxy.message(xml)

	def sendVCard(self, id, info, user = None):
		" Send vCard to client. Info is map with params "
		r = XMLNode('iq', { 'to': self.resource, 'id': id, 'type': 'result' })
		if user:
			r.attrs['from'] = user
		vcard = XMLNode('vCard', { 'xmlns':"vcard-temp" })
		for n in info:
			node = XMLNode(n)
			if isinstance(info[n], list):
				node.nodes.extend(info[n])
			else:
				node.nodes.append(info[n])
			vcard.nodes.append(node)
		r.nodes.append(vcard)

		self.send(r.toString(pack = True))

	def sendRoster(self, id, rost):
		" Send roster to client. Roster is a list of tupples: (user, FN, subscription, [group]) "
		r = XMLNode('iq', { 'to': self.resource, 'id': id, 'type': 'result'})
		roster = XMLNode('query', {'xmlns': 'jabber:iq:roster'})
		r.nodes.append(roster)

		for u in rost:
			item = XMLNode('item', { 'name': u[1], 'jid': u[0], 'subscription': u[2] })
			if len(u) > 3:
				item.nodes.append(XMLNode('group'))
				item['group'].nodes.append(u[3])

			roster.nodes.append(item)

		self.send(r.toString())

	def sendPresence(self, user, status, msg = None, show = None):
		" Send presence of user to client "
		if not msg:
			msg = status
		r = XMLNode('presence', { 'from': user, 'to': self.resource})
		if status != 'online':
			r.attrs['type'] = status
		if show:
			r.nodes.append(XMLNode('show'))
			r['show'].nodes.append(show)
		r.nodes.append(XMLNode('status'))
		r['status'].nodes.append(msg)

		self.send(r.toString(pack=True))

	def sendSubscribe(self, user):
		" Send simple subscription presence to user "
		r = XMLNode('presence', {'from': user, 'type': 'subscribed'})
		self.send(r.toString(pack=True))

	def sendUnsubscribe(self, user):
		" Remove subscription from user: "
		r = XMLNode('presence', {'from': user, 'type': 'unsubscribed'})
		self.send(r.toString(pack=True))

	def sendSubscriptionRequest(self, from_):
		" Send subscription request to client "
		r = XMLNode('presence', { 'type': 'subscribe', 'from': from_ })
		self.send(r.toString(pack = True))

	def idle(self):
		self.proxy.idle()

