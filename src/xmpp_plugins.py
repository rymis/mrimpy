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

import xmlstream
from xmlstream import XMLNode
from traceback import print_exc

class IQError(Exception):
	pass

class IQ(object):
	IQTYPE = ""

	def processIQ(self, xml, client):
		" Process IQ "
		r = self.prepareError(xml, client)
		r['error'].nodes.append(XMLNode("feature-not-implemented", {"xmlns":"urn:ietf:params:xml:ns:xmpp-stanzas"}))
		client.send(r.toString(pack = True))

	def prepareResult(self, xml, client):
		" Makes template of result IQ "
		r = XMLNode("iq")
		if xml.attrs.has_key('id'):
			r.attrs['id'] = xml.attrs['id']

		if client.resource:
			r.attrs['to'] = client.resource

		r.attrs['type'] = 'result'

		return r

	def prepareError(self, xml, client, reason = 'unknown-error'):
		" Makes template of error result "
		r = self.prepareResult(xml, client)
		r.attrs['type'] = 'error'

		r.nodes.extend(xml.nodes)
		r.nodes.append(XMLNode('error'))
		r['error'].nodes.append(XMLNode(reason))

		return r

	def getFeatures(self):
		" Get supported features or None "
		return None

class Bind(IQ):
	IQTYPE = "bind"

	def processIQ(self, xml, client):
		if not xml['bind']['resource']:
			r = self.prepareError(xml, client)
			r['error'].nodes.append(XMLNode("bad-request"))
			return r
		res = None
		for c in xml['bind']['resource'].nodes:
			if isinstance(c, basestring):
				res = c
				break
		if not res:
			r = self.prepareError(xml, client)
			r['error'].nodes.append(XMLNode("bad-request"))
			return r

		print "Client wan't bind to %s" % res

		r = self.prepareResult(xml, client)
		bnd = XMLNode("bind", {"xmlns": 'urn:ietf:params:xml:ns:xmpp-bind'})
		bnd.nodes.append(XMLNode("jid"))
		client.resource = "%s@%s/%s" % (client.user, client.from_, res)
		bnd["jid"].nodes.append(client.resource)
		r.nodes.append(bnd)

		client.send(r.toString(pack = True))


	def getFeatures(self):
		return XMLNode("bind", {"xmlns": "urn:ietf:params:xml:ns:xmpp-bind"})

class Session(IQ):
	IQTYPE = "session"

	def processIQ(self, xml, client):
		r = self.prepareResult(xml, client)
		client.send(r.toString())

	def getFeatures(self):
		return XMLNode("session", {"xmlns": "urn:ietf:params:xml:ns:xmpp-session"})

class vCard(IQ):
	IQTYPE = "vCard"

	def processIQ(self, xml, client):
		if xml.attrs['type'] == 'get':
			try:
				if xml.attrs.has_key('to'):
					to = xml.attrs['to']
				else:
					to = None
				client.proxy.vCardRequest(xml.attrs['id'], to)
			except:
				print_exc()
				r = self.prepareError(xml, client)
				client.send(r.toString())
		else:
			r = self.prepareError(xml, client)
			client.send(r.toString())

class Query(IQ):
	IQTYPE = "query"

	def processIQ(self, xml, client):
		q = xml.nodes[0]
		print "Query:\n%s" % xml.toString()
		if q.attrs['xmlns'] == 'jabber:iq:roster':
			return self.processRoster(xml, client)
		else:
			r = self.prepareError(xml, client)
			client.send(r.toString())

	def processRoster(self, xml, client):
		if not xml.attrs.has_key('type'):
			r = self.prepareError(xml, client, reason = 'invalid-stanza')
			client.send(r.toString())

		if xml.attrs['type'] == 'get':
			try:
				client.proxy.rosterRequest(xml.attrs['id'])
			except:
				print_exc()
				r = self.prepareError(xml, client)
				client.send(r.toString())
		elif xml.attrs['type'] == 'set':
			for n in xml['query']:
				if isinstance(n, XMLNode) and n.name == 'item':
					if n.attrs.has_key('subscription') and n.attrs['subscription'] == 'remove':
						# User wan't remove subscription
						if n.attrs.has_key('jid'):
							client.proxy.rosterRemove(xml.attrs['id'], n.attrs['jid'])
					else:
						# Update roster item:
						client.proxy.rosterUpdate(xml.attrs['id'], n)
		else:
			r = self.prepareError(xml, client)
			client.send(r.toString())

PLUGINS = [ IQ, Bind, Session, vCard, Query ]

