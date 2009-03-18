#!/usr/bin/env python

"""
Simple XML stream parsing library
"""

import re
try:
	from cStringIO import StringIO
except:
	from StringIO import StringIO

_name = '[a-zA-Z_][^<>&= \\s]*'

_preambule = re.compile('(<\\?[^>\\?]*\\?>)\\s*', flags = re.M | re.S)
_stream = re.compile('<(?P<stream>' + _name + ')[^<>&]*>', flags = re.M | re.S)
_fulltag = re.compile('\\s*<(?P<tname>' + _name + ').*</(?P=tname)[^<>&]*>\\s*', flags = re.M | re.S)
_fulltag_one = re.compile('\\s*<' + _name + '[^<>&]*/>', flags = re.M | re.S)

_comment = re.compile('\\s*<!--.*-->\\s*', re.M | re.S)

class XMLNode(object):
	def __init__(self):
		self.attrs = {}
		self.nodes = []
		self.characters = ""

class XMLInputStream(object):
	def __init__(self):
		" Create new XML input stream "
		self.buf = ""

		self._preambule = None
		self._stream = None
		self._namespace = None
		self._close_stream = None

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
				if not m:
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
		print xml

	def _stream_start(self, m):
		print "Stream start"
		stream_name = m.group('stream')
		self._close_stream = re.compile('\\s*</%s>' % stream_name)

	def _stream_close(self, xml):
		print "Close stream"

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



