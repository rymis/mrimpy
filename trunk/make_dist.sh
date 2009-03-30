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
rm -rf mrimpy-$VERSION/mail.ru
tar cjvf mrimpy-$VERSION.tbz mrimpy-$VERSION

echo -n "Do you wan't to upload this file? [yn]"
read ans

case $ans in
	[yY]*)
		# Upload to GoogleCode:
		[ -f googlecode_upload.py ] || wget http://support.googlecode.com/svn/trunk/scripts/googlecode_upload.py
		python googlecode_upload.py -s "MRIM to Jabber gateway, v.$VERSION" -p "mrimpy" mrimpy-$VERSION.tbz
	;;
esac

