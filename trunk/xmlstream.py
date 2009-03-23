#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Simple XML stream parsing library
"""

import re
try:
	from cStringIO import StringIO
except:
	from StringIO import StringIO
import xml.sax, xml.sax.handler
from xml.sax.saxutils import escape as xml_escape

_name = '[a-zA-Z_][^<>&= \\s]*'

_preambule = re.compile('(<\\?[^>\\?]*\\?>)\\s*', flags = re.M | re.S)
_stream = re.compile('<(?P<stream>' + _name + ')[^<>&]*>', flags = re.M | re.S)
_fulltag = re.compile('\\s*<(?P<tname>' + _name + ').*</(?P=tname)[^<>&]*>\\s*', flags = re.M | re.S)
_fulltag_one = re.compile('\\s*<' + _name + '[^<>&]*/>', flags = re.M | re.S)

_comment = re.compile('\\s*<!--.*-->\\s*', re.M | re.S)

def _utfstring(s):
	if isinstance(s, unicode):
		return s.encode('utf-8', 'replace')
	return s

class XMLError(Exception):
	pass

class XMLNode(object):
	"""
	XMLNode is simple XML manipulation API. Usage:
xml = parseXML('<a h="b"><b a="a"></b></a>')
xml['b'].nodes.append(XMLNode(name = "c", attrs = { "x": "y" }))
xml['b']['c'].nodes.append('string')
print xml.toString()
	"""
	def __init__(self, name = None, attrs = None, orig = None):
		" Create new XMLNode instance "
		self.name = name
		if not attrs:
			self.attrs = {}
		else:
			self.attrs = attrs
		self.nodes = []
		self.orig = orig

	def __getitem__(self, name):
		" Get subnode: "
		for node in self.nodes:
			if isinstance(node, XMLNode) and node.name == name:
				return node
		return None

	def _quoteattr(self, s):
		return s.replace('"', '&quot;')

	def toString(self, align = 4, pack = False, _offset = 0, _S = None, noclose = False):
		" Returns string representation of XML. No <?xml...> provided and encoding is always utf-8 "

		if not _S:
			S = StringIO()
		else:
			S = _S

		margin = ' ' * (_offset * align)
		if not pack:
			S.write(margin)
		S.write('<%s' % _utfstring(self.name))
		for a in self.attrs:
			S.write(' %s="%s"' % (_utfstring(a), _utfstring(self._quoteattr(self.attrs[a]))))
		if len(self.nodes) == 0:
			if not noclose:
				S.write('/>')
			else:
				S.wirte('>')
		else:
			S.write('>')
			if not pack:
				S.write('\n')
			for node in self.nodes:
				if isinstance(node, basestring):
					# Characters:
					if not pack:
						S.write(margin)
						S.write(' ' * align)
					S.write(xml_escape(_utfstring(node).strip()))
					if not pack:
						S.write('\n')
				else:
					node.toString(align, pack, _offset + 1, S)

			if not noclose:
				if not pack:
					S.write(margin)
				S.write('</%s>' % _utfstring(self.name))
		if not pack:
			S.write('\n')

		return S.getvalue()

	def __str__(self):
		return self.toString()

class _XMLParser(xml.sax.handler.ContentHandler):
	# XML parser private class
	def __init__(self):
		self.tree = []

	def startElement(self, name, attrs):
		# create new node:
		ats = {}
		for a in attrs.keys():
			ats[a] = attrs[a]
		node = XMLNode(name, ats)
		self.tree.append(node)

	def endElement(self, name):
		if len(self.tree) == 1:
			# This is the result
			return
		prev = self.tree[-2]
		last = self.tree[-1]

		if last.name != name:
			raise XMLError, "Invalid closing tag"

		prev.nodes.append(last)
		del self.tree[-1]

	def characters(self, data):
		d = data.strip()
		if len(d) == 0:
			return

		if len(self.tree[-1].nodes) > 0 and isinstance(self.tree[-1].nodes[-1], basestring):
			self.tree[-1].nodes[-1] += d
		else:
			self.tree[-1].nodes.append(d)

def parseXML(xmls):
	" Parse XML to XMLNode from string "
	parser = _XMLParser()
	xml.sax.parseString(xmls, parser)
	parser.tree[0].orig = xmls
	return parser.tree[0]

class XMLInputStream(object):
	def __init__(self):
		" Create new XML input stream "
		self.buf = ""

		self._preambule = None
		self._stream = None
		self._namespace = None
		self._close_stream = None

		self.h_start = []
		self.h_stanza = []
		self.h_end = []

	def data(self, dat):
		" This method called when new data received "
		self.buf += dat
		self._process_data()

	def _process_data(self):
		" Process buffer "
		cont = True
		while cont:
			l = len(self.buf)
			if self._stream:
				# The stream is started:
				m = _fulltag.match(self.buf)
				if m:
					cname = "</%s>" % m.group('tname')
					first = self.buf.find(cname)
					if first < 0:
						raise XMLError, "Can not parse XML"
					xml = self._preambule + self.buf[:first + len(cname)]
					self.buf = self.buf[first + len(cname):]
					self._next_xml(xml)
				else:
					m = _fulltag_one.match(self.buf)
					if m:
						xml = self._preambule + self.buf[:m.end(0)]
						self.buf = self.buf[m.end(0):]
						self._next_xml(xml)

				m = self._close_stream.match(self.buf)
				if m:
					xml = self.buf[:m.end(0)]
					self.buf = self.buf[m.end(0):]
					self._stream_close(xml)

				m = _comment.match(self.buf)
				if m:
					xml = self.buf[:m.end(0)]
					self.buf = self.buf[m.end(0):]
			else:
				if not self._preambule:
					m = _preambule.match(self.buf)
					if m:
						self._preambule = self.buf[:m.end(0)]
						self.buf = self.buf[m.end(0):]

				m = _stream.match(self.buf)
				if m:
					self._stream = self.buf[:m.end(0)]
					self.buf = self.buf[m.end(0):]
					self._stream_start(m)

			cont = (l != len(self.buf))


	def _next_xml(self, xml):
		x = parseXML(xml)
		for h in self.h_stanza:
			if not h(x):
				return False
		return True

	def _stream_start(self, m):
		stream_name = m.group('stream')
		self._close_stream = re.compile('\\s*</%s>' % stream_name)

		stag = "%s</%s>"  % (m.group(0), stream_name)
		x = parseXML(stag)

		for h in self.h_start:
			if not h(stream_name.split(':')[0], x.attrs):
				return False
		return True

	def restart(self):
		""" Restart stream, so waiting for <?xml version="1.0"?><stream:stream> """
		self._preambule = None
		self._stream = None
		self._process_data()

	def _stream_close(self):
		for h in self.h_end:
			if not h():
				return False
		return True

class XMLOutputStream(object):
	" Output stream of XML"

	def __init__(self, namespace = None):
		self.namespace = namespace

	def startStream(self):
		pass

	def endStream(self):
		pass

	def formatTag(self, name, attrs = {}, inner = None):
		S = StringIO()
		if self.namespace:
			nm = "%s:%s" % (namespace, name)
		else:
			nm = name

		S.write("<%s" % nm)
		for a in attrs:
			S.write(' %s="%s"' % (a, attrs[a]))

		if inner:
			S.write('>%s</%s>' % (inner, nm))
		else:
			S.write('/>')

		return S.get_value()



if __name__ == '__main__':
	import sys
	for a in sys.argv[1:]:
		X = XMLInputStream()
		X.data(open(a, 'rt').read())

	# Speed test:
	from random import choice
	names = [ "a", "b", "c", "d", "e", "f", "g" ]

	X = XMLInputStream()
	X.data('<?xml version="1.0"?><stream:stream>')
	for i in xrange(100000):
		if (i % 1000) == 0:
			print "[%d%%]" % (int(i)/1000)
		a = {}
		for n in names:
			a[n] = choice(names)
		x = XMLNode(choice(names), a)

		for j in xrange(5):
			a = {}
			for n in names:
				a[n] = choice(names)
			y = XMLNode(choice(names), a)
			x.nodes.append(y)
		X.data(x.toString())

