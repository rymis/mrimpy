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
import shelve
from traceback import print_exc
try:
	import cPickle as pickle
except:
	import pickle

# Trying to determine mydir and data dir:
RUNPATH = os.path.abspath(os.curdir)

if os.path.isdir(os.path.join(RUNPATH, '..', 'share', 'mrimpy')):
	DATAPATH = os.path.abspath(os.path.join(RUNPATH, '..', 'share', 'mrimpy', 'data'))
elif os.path.isdir(os.path.join(RUNPATH, 'data')):
	DATAPATH = os.path.abspath(os.path.join(RUNPATH, 'data'))
else:
	DATAPATH = RUNPATH

# Determine home:
if os.environ.has_key('HOME'):
	HOMEPATH = os.environ['HOME']
elif os.environ.has_key('HOMEPATH'):
	if not os.environ.has_key('HOMEDRIVE'):
		hd = 'C:'
	else:
		hd = os.environ['HOMEDRIVE']
	HOMEPATH = os.path.join(hd, os.environ['HOMEPATH'])
elif os.environ.has_key('WINDIR'):
	HOMEPATH = os.environ['WINDIR']
else:
	HOMEPATH = RUNPATH

class GladeWrapper(object):
	def __init__(self, glade):
		self._glade = glade

	def __getattr__(self, name):
		return self._glade.get_widget(name)

	def autoconnect(self, *args):
		self._glade.signal_autoconnect(*args)

class mem_storage(dict):
	def __init__(self):
		dict.__init__(self)

	def close(self):
		pass

	def sync(self):
		pass

class Config(object):
	def __init__(self, appname):
		self.appname = appname
		self.options = mem_storage()
		self.contacts = mem_storage()
		self.history = None
		self._dirname = self.__cfg_dir(appname)
		if self._dirname:
			try:
				self.options = shelve.open(os.path.join(self._dirname, 'options.slv'), 'c')
			except:
				print "Warning: can't open config, using memory configuration"
				print_exc()
				self.options = mem_storage()

			try:
				self.contacts = shelve.open(os.path.join(self._dirname, 'contacts.slv'), 'c')
			except:
				print "Warning: can't open contacts cache, using memory configuration"
				print_exc()
				self.contacts = mem_storage()

			try:
				self.history = None
			except:
				self.history = None # Don't use history
		else:
			print "WARNING: Can not open configuration directory. Using memory configuration"

	def sync(self):
		" Save options: "
		self.options.sync()
		self.contacts.sync()

	def close(self):
		" Sync and exit "
		self.sync()
		self.options.close()
		self.contacts.close()

	def __cfg_dir(self, appname):
		p = os.path.join(HOMEPATH, '.%s' % appname)
		if not os.path.isdir(p):
			try:
				os.makedirs(p, 0700)
			except:
				return None
		return p

	def __getitem__(self, name):
		if self.options.has_key(name):
			return self.options[name]
		else:
			return None

	def __setitem__(self, name, val):
		self.options[name] = val

	def history_add(self, message):
		" Add message to history "
		# TODO
		pass

def load_glade(name):
	" Load glade from file "
	# TODO:
	if not name.endswith('.glade'):
		name = name + '.glade'
	return GladeWrapper(gtk.glade.XML(name))

class ChatBody(gtk.VBox):
	def __init__(self, address, nickname):
		gtk.VBox.__init__(self)
		self.address = address
		self.nickname = nickname
		self.chat = gtk.TextView()
		self.msg = gtk.TextView()
		self.pack_start(self.chat, True, True, 4)
		self.pack_start(self.msg, False, True, 4)
		self.msg.connect('key-press-event', self._check_enter)
		self.mrim = None

	def _check_enter(self, w, event):
		if event.keyval == gtk.keysyms.Return:
			self._send_message()
			return True
		else:
			return False

	def _send_message(self):
		print "Sending message..."

class message_window(object):
	def __init__(self, parent, mrim):
		self.mrim = mrim
		self.glade = load_glade('message_window')
		# self.glade.window.set_parent(parent)
		self.glade.window.set_destroy_with_parent(True)

		self.glade.autoconnect(self)

	def show(self):
		self.glade.window.show_all()
		self.glade.window.present()

	def hide(self):
		self.glade.window.hide()

	def add_chat(self, address, nickname):
		" Add chat tab. If exist - activate it "
		try:
			self.activate_chat(address)
			return True
		except:
			pass

		lbl = self._create_chat_label(address, nickname)
		body = ChatBody(address, nickname)
		body.mrim = self.mrim

		self.glade.notebook.append_page(body, lbl)

	def add_message(self, msg):
		self.add_chat(msg['From'])
		# TODO:


	def _create_chat_label(self, address, nickname):
		lbl = gtk.Label(address)
		lbl._address = address
		return lbl

	def window_delete_event_cb(self, w, d):
		return w.hide_on_delete()

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
		self.mrim.add_handler('contact_list', self.contact_list_received)
		self.mrim.add_handler('offline_message', self.offline_message)

		self.name = None
		self.password = None
		self.save_password = False

		gobject.idle_add(self._idle)

		self.__init_treeview(self.glade.contacts)
		self.__init_status(self.glade.status)

		self._clist = self.config['contact_list']
		if not self._clist:
			self._clist = ([], [])
		for g in self._clist[1]:
			for c in g:
				c['status'] = mrim.STATUS_OFFLINE
		self.contact_list_received(*self._clist)

		self.glade.autoconnect(self)

		s = self.config['window_size']
		if s:
			self.glade.window1.set_size_request(*s)

		self.name = self.config['name']
		self.save_password = self.config['save_password']
		if self.save_password:
			self.password = self.config['password']

		self.msg_wnd = message_window(self.glade.window1, self.mrim)

		self.glade.window1.show_all()

	def _idle(self):
		try:
			self.mrim.idle()
		except:
			print "Unknown error in idle function"
			print_exc()
		return True

	def wnd_destroy(self, w):
		# w = self.glade.window1
		self.config['contact_list'] = self._clist
		self.config['name'] = self.name
		self.config['save_password'] = self.save_password
		if self.save_password:
			self.config['password'] = self.password
		else:
			self.config['password'] = None

		self.config.close()
		gtk.main_quit()

	def contacts_row_activated_cb(self, w, path, clmn):
		model = self.glade.contacts.get_model()
		iter = model.get_iter(path)
		address = model.get(iter, 1)[0]
		nickname = address # TODO: real nickname

		self.msg_wnd.add_chat(address, nickname)
		self.msg_wnd.show()

	def menu_quit(self, w):
		self.config['window_size'] = self.glade.window1.get_size()
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

		self._clist = (groups, contacts)

	def offline_message(self, msg):
		from = msg['From']
		self.msg.show()
		self.msg.add_message(msg)

if __name__ == '__main__':
	wnd = main_window()
	gtk.main()

