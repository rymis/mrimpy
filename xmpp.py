#!/usr/bin/env python

"""
	Simple XML Stream implementation in Python.
"""

class XMPPError(Exception):
	pass

class IOStream(object):
	" IO stream base object. Provide buffered read and write of characters, lines, ... "
	BUFSIZ = 8192

	def __init__(self):
		" Initialize stream "
		self._write_buf = ""
		self._read_buf = ""
		self._read_pos = 0

	def _read(self, len):
		" Each stream must implement this method, if we can read from it "
		raise XMPPError, "Stream has no read capabilities"

	def _write(self, buf):
		" Each stream must implement this method if we can write to stream "
		raise XMPPError, "Stream has no write capabilities"

	def _can_read(self):
		return False

	def _can_write(self):
		return False

	def getc(self):
		" read one character from stream "
		if self._read_pos < len(self._read_buf):
			self._read_pos += 1
			return self._read_buf[self._read_pos]
		self._read_buf = self._read(self.BUFSIZ)
		if len(self._read_buf) == 0:
			self._read_pos = 0
			return None
		self._read_pos = 1
		return self._read_buf[0]

	def puts(self, s):
		" write string to stream: "
		self._write_buf += s
		if len(self._write_buf) > self.BUFSIZ:
			l = self._write(self._write_buf)
			if l < 0:
				raise XMPPError, "Write error"
			self._write_buf = self._write_buf[l:]

class XMLStream(object):
	" XML stream object. Read and write XML streams "

	def __init__(self, read, write = None):
		" Init new instance of XML stream: "
