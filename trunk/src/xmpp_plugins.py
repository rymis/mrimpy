#!/usr/bin/env python

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

	def prepareError(self, xml, client):
		" Makes template of error result "
		r = self.prepareResult(xml, client)
		r.attrs['type'] = 'error'

		r.nodes.extend(xml.nodes)
		r.nodes.append(XMLNode('error'))

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
				client.proxy.vCardRequest(xml.attrs['id'])
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
		if xml.attrs['type'] == 'get':
			try:
				client.proxy.rosterRequest(xml.attrs['id'])
			except:
				print_exc()
				r = self.prepareError(xml, client)
				client.send(r.toString())
		else:
			r = self.prepareError(xml, client)
			client.send(r.toString())

PLUGINS = [ IQ, Bind, Session, vCard, Query ]

