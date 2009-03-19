#!/usr/bin/env python

# Main module of Jabber2MRIM gateway.

import eserver
import xmpp
import xmlstream
import random

class Jabber2MRIM(eserver.Protocol):
	def __init__(self, sock, server):
		super(Jabber2MRIM, self).__init__(sock, server)

		self.xml = xmlstream.XMLInputStream()
		self.xml.h_start.append(self.startStream)
		self.xml.h_stanza.append(self.xmlReceive)
		self.xml.h_end.append(self.endStream)

		self.id = str(random.randint(100000000, 999999999))
		self.from_ = None

	def startStream(self, ns, attrs):
		self.from_ = attrs['to']
		self.namespace = ns
		self.send(
"""<%s:stream from="%s" id="%s" version="1.0" xmlns:stream="http://etherx.jabber.org/streams" xmlns="jabber:client">
<stream:features>
<mechanisms xmlns="urn:ietf:params:xml:ns:xmpp-sasl">
<mechanism>PLAIN</mechanism>
</mechanisms>
</stream:features>""" % (self.namespace, self.from_, self.id))

	def endStream(self):
		print "The End!"

	def processData(self, buf):
		self.xml.data(buf)

	def xmlReceive(self, xml):
		print xml.toString()


if __name__ == '__main__':
	S = eserver.EventServer( ('localhost', 5222), Jabber2MRIM )
	S.start()
