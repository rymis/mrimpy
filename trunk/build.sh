#!/bin/sh

python util/gen_mk.py
autoconf

if [ -x ./config.status ]; then
	./config.status
else
	./configure
fi

