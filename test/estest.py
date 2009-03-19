#!/usr/bin/env python

# EventServer test
import eserver
import sys

class EchoProtocol(eserver.Protocol):
	def processData(self, data):
		self.send(data)

def main(argv):
	S = eserver.EventServer( ('localhost', 9999), EchoProtocol )
	S.start()

if __name__ == '__main__':
	main(sys.argv)
