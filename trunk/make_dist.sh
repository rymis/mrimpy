#!/bin/sh

VERSION=0.2

if [ "x$1" = "xinc" ]; then
	# Increment version
	vM=`echo $VERSION | sed 's/\\..*$//'`
	vm=`echo $VERSION | sed 's/^[^\\.]*\\.//'`
	vm=`expr $vm + 1`
	echo "New version is: $vM.$vm"
	cat "$0" | sed "s/^VERSION=.*$/VERSION=$vM.$vm/" > "$0.tmp"
	mv "$0" "$0.back"
	mv "$0.tmp" "$0"
	echo "Backup saved to: $0.back"
	exit 0
fi

# Create distfile:
mkdir DIST
cd DIST
svn checkout http://mrimpy.googlecode.com/svn/trunk/ mrimpy-read-only
mv mrimpy-read-only mrimpy-$VERSION
find mrimpy-$VERSION -name ".svn" -exec rm -rf {} \;
rm -rf mrimpy-$VERSION/data
rm -rf mrimpy-$VERSION/glade
tar cjvf mrimpy-$VERSION.tbz mrimpy-$VERSION

