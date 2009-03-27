#!/bin/sh

VERSION=0.01

# Create distfile:
mkdir DIST
cd DIST
svn checkout http://mrimpy.googlecode.com/svn/trunk/ mrimpy-read-only
mv mrimpy-read-only mrimpy-$VERSION
find mrimpy-$VERSION -name ".svn" -exec rm -rf {} \;
tar cjvf mrimpy-$VERSION.tbz mrimpy-$VERSION

