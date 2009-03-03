#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
	Very simple GTK+ MRIM client.
"""

import gtk
import gtk.glade
import gobject
import mrim
import os, os.path
import sys
import traceback
try:
	import cPickle as pickle
except:
	import pickle


class GladeWrapper(object):
	def __init__(self, glade):
		self._glade = glade

	def __getattr__(self, name):
		return self._glade.get_widget(name)

	def autoconnect(self, *args):
		self._glade.signal_autoconnect(*args)

class Config(object):
	def __init__(self, appname = None):
		self.appname = appname
		self.options = {}
		if appname:
			self.load()

	def __cfg_name(self, appname):
		if os.environ.has_key('HOME'):
			return os.path.join(os.environ['HOME'], '.%s' % appname)
		else:
			return os.path.abspath(os.curdir, '%s.cfg' % appname)

	def save(self, appname = None):
		if not appname:
			appname = self.appname
		f = open(self.__cfg_name(appname), 'wb')
		pickle.dump(self.options, f)
		f.close()

	def load(self, appname = None):
		if not appname:
			appname = self.appname
		try:
			f = open(self.__cfg_name(appname), 'rb')
			self.options = pickle.load(f)
			f.close()
		except:
			self.options = {}

	def __getitem__(self, name):
		if self.options.has_key(name):
			return self.options[name]
		else:
			return None

	def __setitem__(self, name, val):
		self.options[name] = val

def load_glade(name):
	" Load glade from file "
	# TODO:
	if not name.endswith('.glade'):
		name = name + '.glade'
	return GladeWrapper(gtk.glade.XML(name))

MRIM_STATUSES = [
		( "Offline", mrim.STATUS_OFFLINE ),
		( "Online", mrim.STATUS_ONLINE )
]

class main_window(object):
	def __init__(self):
		self.config = Config('gmrim')
		self.glade = load_glade("main_window")
		self.mrim = mrim.MailRuAgent()
		self.mrim.add_handler('user_info', self.mrim_user_info)
		self.mrim.add_handler('contact_list_received', self.contact_list_received)

		self.name = None
		self.password = None
		self.save_password = False

		gobject.idle_add(self._idle)

		self.__init_treeview(self.glade.contacts)
		self.__init_status(self.glade.status)

		if self.config['contact_list']:
			self._contact_list = self.config['contact_list']
			self.contact_list_received(*self._contact_list)
		else:
			self._contact_list = ([], [])

		self.glade.autoconnect(self)

		s = self.config['window_size']
		if s:
			self.glade.window1.set_size_request(*s)

		self.name = self.config['name']
		self.save_password = self.config['save_password']
		if self.save_password:
			self.password = self.config['password']

		self.glade.window1.show_all()

	def _idle(self):
		try:
			self.mrim.idle()
		except:
			print "Unknown error in idle function"
			traceback.print_exc()
		return True

	def wnd_destroy(self, w):
		# w = self.glade.window1
		self.config['window_size'] = w.get_size()

		self.config['name'] = self.name
		self.config['save_password'] = self.save_password
		if self.save_password:
			self.config['password'] = self.password
		else:
			self.config['password'] = None
		self.config['contact_list'] = self._contact_list

		self.config.save()
		gtk.main_quit()

	def menu_quit(self, w):
		self.glade.window1.destroy()

	def __init_treeview(self, tv):
		# TODO: status as icon, avatars...
		model = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		tv.set_model(model)

		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("status", renderer, text = 0)
		tv.append_column(column)

		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("id", renderer, text = 1)
		tv.append_column(column)

	def __init_status(self, st):
		# TODO: icon
		model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_INT)
		st.set_model(model)
		renderer = gtk.CellRendererText()
		st.pack_start(renderer, True)
		st.add_attribute(renderer, 'text', 0)

		for i in MRIM_STATUSES:
			iter = model.append(None)
			model.set(iter, 0, i[0], 1, i[1])

		iter = model.get_iter_first()
		st.set_active_iter(iter)

	def add_contact(self, id):
		" add contact to list: "
		model = self.glade.contacts.get_model()
		iter = model.append(None)
		model.set(iter, 1, id)

	def remove_contact(self, id):
		" remove this contact from list "
		# TODO
		pass

	def set_contact_status(self, id, status):
		" set contact status "
		# TODO
		pass

	def status_changed(self, w):
		st = self.glade.status

		model = st.get_model()
		iter = st.get_active_iter()

		status = model.get(iter, 1)[0]

		if status == mrim.STATUS_OFFLINE:
			self.mrim.close()
		else:
			if not self.mrim.is_connected():
				self.connect(status = status)
			else:
				self.mrim.change_status(status)

	def connect(self, status = mrim.STATUS_ONLINE):
		" Connect. If need answere for name and password "
		if not self.name or not self.password:
			if not self.ask_pass():
				# TODO: set status to offline
				return None

		print "Connecting to MRIM..."
		self.mrim.connect(self.name, self.password, status = status)
		print "Connected..."

	def ask_pass(self):
		dlg = gtk.Dialog("Enter password:", self.glade.window1, gtk.DIALOG_MODAL, (gtk.STOCK_OK, gtk.RESPONSE_OK, gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
		name = gtk.Entry()
		passwd = gtk.Entry()
		passwd.set_visibility(False)

		if self.name:
			name.set_text(self.name)
		save = gtk.CheckButton("Save password")

		tbl = gtk.Table(3, 2)
		tbl.attach(gtk.Label("Name:"), 0, 1, 0, 1)
		tbl.attach(name, 1, 2, 0, 1)
		tbl.attach(gtk.Label("Password:"), 0, 1, 1, 2)
		tbl.attach(passwd, 1, 2, 1, 2)
		tbl.attach(save, 1, 2, 2, 3)

		dlg.vbox.add(tbl)
		tbl.show_all()

		res = dlg.run()
		if res == gtk.RESPONSE_OK:
			self.name = name.get_text()
			self.password = passwd.get_text()
			self.save_password = save.get_active()
			dlg.destroy()
			return True
		else:
			dlg.destroy()
			return False


	def mrim_user_info(self, msg, info):
		print "UI: %s" % repr(info)

	def contact_list_received(self, groups, contacts):
		# Create contact list:
		def my_del(model, path, iter, user_data):
			model.remove(iter)
			return False

		self.glade.contacts.foreach(my_del, None)

		M = self.glade.contacts.get_model()
		for g, cl in zip(groups, contacts):
			giter = M.append(None)
			M.set(giter, 1, "%s (%d)" % (g['name'], len(cl)))

			for c in cl:
				iter = M.append(giter)
				M.set(iter, 0, "%d" % c['status'], 1, c['address'])

		self._contact_list = (groups, contacts)



if __name__ == '__main__':
	wnd = main_window()
	gtk.main()

