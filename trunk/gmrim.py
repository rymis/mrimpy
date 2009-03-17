#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
	Very simple GTK+ MRIM client.
"""

import gtk
import gtk.glade
import gtk.gdk
import gobject
import pango
import mrim
import os, os.path
import sys
import shelve
import datetime
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
GLOBAL_THEME = 'stellar'

class GladeWrapper(object):
	def __init__(self, glade):
		self._glade = glade

	def __getattr__(self, name):
		return self._glade.get_widget(name)

	def autoconnect(self, *args):
		self._glade.signal_autoconnect(*args)

def get_icon_name(name):
	" Get icon name with specified theme "
	for ext in [ '.gif', '.png', '.jpg', "" ]:
		fn = os.path.join(DATAPATH, 'icons', GLOBAL_THEME, "%s%s" % (name, ext))
		if os.path.isfile(fn):
			return fn
	return None

def load_icon(name):
	nm = get_icon_name(name)
	if nm:
		return gtk.gdk.pixbuf_new_from_file(nm)
	return None

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

def ErrorMessage(parent, msg, traceback = False):
	" Show error message and optionally python traceback "
	dlg = gtk.MessageDialog(parent, gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, msg)
	dlg.run()
	dlg.hide()

class ChatBody(gtk.VBox):
	# TODO: from config
	in_color = 'brown'
	out_color = 'blue'

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
		self.chat.set_editable(False)
		buf = self.chat.get_buffer()

		buf.create_tag("italic", style=pango.STYLE_ITALIC)
		buf.create_tag("bold", weight=pango.WEIGHT_BOLD)
		buf.create_tag("outgoing", foreground = self.out_color)
		buf.create_tag("incoming", foreground = self.in_color)
		buf.create_tag("monospace", family="monospace")

		self.send_message = None

	def _check_enter(self, w, event):
		if event.keyval == gtk.keysyms.Return:
			self._send_message()
			self.msg.get_buffer().set_text("")
			return True
		else:
			return False

	def _send_message(self):
		b = self.msg.get_buffer()
		msg_txt = b.get_text(b.get_start_iter(), b.get_end_iter(), False)
		print repr(msg_txt.decode('utf-8'))
		if self.send_message:
			s = self.send_message
			s(msg_txt, self.address)

class message_window(object):
	def __init__(self, parent, mrim):
		self.mrim = mrim
		self.glade = load_glade('message_window')
		self.glade.window.set_transient_for(parent)
		self.glade.window.set_destroy_with_parent(True)

		self.glade.window.set_size_request(640, 480) # TODO: size from config as in main window

		self.glade.autoconnect(self)

	def show(self):
		self.glade.window.show_all()
		self.glade.window.present()

	def hide(self):
		self.glade.window.hide()

	def add_chat(self, address, nickname = '', my_nick = 'You'):
		" Add chat tab. If exist - activate it "
		try:
			if self.activate_chat(address):
				return True
		except:
			pass

		lbl = self._create_chat_label(address, nickname)
		body = ChatBody(address, nickname)
		body.send_message = self.send_message
		body.mrim = self.mrim

		self.glade.notebook.append_page(body, lbl)
		self.glade.notebook.set_current_page( -1 ) # It is not work, but will be for feature

	def add_message(self, msg, address = None, direction = 'C2S', date = None):
		" Add message to chat and history. Direction is string 'C2S' or 'S2C' "
		# TODO: XML message
		if isinstance(msg, mrim.MRIMMessage):
			address = msg.address
			msg = msg.msg
		elif isinstance(msg, str):
			msg = msg.decode('utf-8', 'replace') # For messages from TextBuffer

		out = (direction == 'C2S')

		if out:
			self.add_chat(address)
			color = 'outgoing'
		else:
			color = 'incoming'
			self.add_chat(address)

		if not date:
			date = datetime.datetime.now()
			sdate = date.time().strftime("%H:%M:%S")
		else:
			d = datetime.datetime.now()
			if d.date() == date.date():
				sdate = date.time().strftime("%H:%M:%S")
			else:
				sdate = date.ctime()

		chat = self.glade.notebook.get_nth_page(self.glade.notebook.get_current_page())
		if out:
			a_from = self.mrim.address
			a_to = chat.address
		else:
			a_to = self.mrim.address
			a_from = chat.address

		buf = chat.chat.get_buffer()
		iter = buf.get_end_iter()

		buf.insert_with_tags_by_name(iter, "[%s] " % sdate, "monospace")
		buf.insert_with_tags_by_name(iter, "%s: " % a_from, color, 'italic')

		# Insert message:
		if not msg.endswith('\n'):
			msg = msg + '\n'
		buf.insert(iter, msg)

	def _insert_rtf(self, buf, iter, rtf_mrim):
		" insert RTF text "
		text = self.mrim.rtf2text(rtf_mrim)
		buf.insert(iter, text_part)

	def _create_chat_label(self, address, nickname):
		lbl = gtk.Label(address)
		lbl._address = address
		return lbl

	def window_delete_event_cb(self, w, d):
		return w.hide_on_delete()

	def activate_chat(self, addr):
		" Activate chat with contact <addr> "
		for i in range(self.glade.notebook.get_n_pages()):
			page = self.glade.notebook.get_nth_page(i)
			if page.address == addr:
				self.glade.notebook.set_current_page(i)
				return True
		return False

	def send_message(self, txt, addr):
		if not self.mrim.is_connected():
			ErrorMessage(self.glade.wnd, "We don't support sending messages until you offline")
			return
		else:
			try:
				seq = self.mrim.send_message(txt, addr)
				# TODO: save seq and wait for reply...
			except:
				ErrorMessage(self.glade.wnd, "Sending message failed")
				return
			self.add_message(txt, address = addr, direction = 'C2S')

class authorization_window(object):
	def __init__(self, parent, msg, cl):
		self.msg = msg
		self.parent = parent
		self.glade = load_glade('auth_req')

		# TODO: message as XML
		self.glade.dlg.set_title("Contact %s request authorization..." % msg.address)
		self.glade.dlg.set_transient_for(parent)
		self.glade.dlg.set_destroy_with_parent(True)
		buf = self.glade.textview.get_buffer()
		buf.set_text(unicode(msg.msg, mrim.MRIM_ENCODING, 'replace'))

		self.glade.autoconnect(self)

		self.glade.dlg.show_all()

	def cancel_clicked(self, w):
		self.glade.dlg.hide()

	def ok_clicked(self, w):
		self.msg.authorize()
		self.glade.dlg.hide()

class authorization_request(object):
	def __init__(self, parent, mrim, cl):
		self.mrim = mrim
		self.parent = parent
		self.contact_list = cl
		self.glade = load_glade('auth_dlg')

		# Add groups:
		model = gtk.ListStore(gobject.TYPE_STRING)
		self.glade.group.set_model(model)
		renderer = gtk.CellRendererText()
		self.glade.group.pack_start(renderer, True)
		self.glade.group.add_attribute(renderer, 'text', 0)
		self.glade.group.set_active(0)

		for g in self.contact_list.groups:
			iter = model.append()
			model.set(iter, 0, g['name'])

		self.glade.autoconnect(self)

		self.glade.dialog.run()

	def cancel_clicked(self, w):
		print "Cancel"

		self.glade.dialog.hide()

	def ok_clicked(self, w):
		addr = self.glade.entry.get_text().decode('utf-8')
		buf = self.glade.textview.get_buffer()
		msg = buf.get_text(buf.get_start_iter(), buf.get_end_iter()).decode('utf-8')

		if len(msg) == 0:
			msg = "Add me to your rouster, please"
		if '@' not in addr:
			ErrorMessage(self.glade.dialog, "Invalid address")
			return

		grp = self.glade.group.get_active()
		self.contact_list.add_contact(addr, grp)

		M = mrim.MRIMMessage(msg = msg, flags = mrim.MESSAGE_FLAG_AUTHORIZE, mrim = self.mrim, address = addr)
		seq = self.mrim.send_message(M)

		self.glade.dialog.hide()


MRIM_STATUSES = [
		( "Offline", mrim.STATUS_OFFLINE, 'offline' ),
		( "Online", mrim.STATUS_ONLINE, 'online' ),
		( "Away", mrim.STATUS_AWAY, 'away' ),
		( "Undeterminated", mrim.STATUS_UNDETERMINATED, 'offline' )
]

class main_window(object):
	def __init__(self):
		self.config = Config('gmrim')
		self.glade = load_glade("main_window")
		self.mrim = mrim.MailRuAgent()
		self.contact_list = mrim.ContactList(self.mrim)
		self.mrim.add_handler('user_info', self.mrim_user_info)
		self.mrim.add_handler('contact_list_updated', self.contact_list_received)
		self.mrim.add_handler('message', self.message_received)
		self.mrim.add_handler('message_status', self.message_status)
		self.mrim.add_handler('authorization_request', self.authorization_received)

		self.name = None
		self.password = None
		self.save_password = False

		gobject.idle_add(self._idle)

		self.__init_treeview(self.glade.contacts)
		self.__init_status(self.glade.status)

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
		model = gtk.TreeStore(gobject.TYPE_OBJECT, gobject.TYPE_STRING)
		tv.set_model(model)

		renderer = gtk.CellRendererPixbuf()
		column = gtk.TreeViewColumn("status", renderer, pixbuf = 0)
		tv.append_column(column)

		renderer = gtk.CellRendererText()
		column = gtk.TreeViewColumn("id", renderer, text = 1)
		tv.append_column(column)

	def __init_status(self, st):
		# TODO: icon
		model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_INT, gobject.TYPE_OBJECT)
		st.set_model(model)

		renderer = gtk.CellRendererPixbuf()
		st.pack_start(renderer, True)
		st.add_attribute(renderer, 'pixbuf', 2)

		renderer = gtk.CellRendererText()
		st.pack_start(renderer, True)
		st.add_attribute(renderer, 'text', 0)

		for i in MRIM_STATUSES:
			iter = model.append(None)
			model.set(iter, 0, i[0], 1, i[1], 2, load_icon(i[2]))

		iter = model.get_iter_first()
		st.set_active_iter(iter)

	def _status_to_icon(self, status):
		for s in MRIM_STATUSES:
			if s[1] == (status & 0xFFFF):
				return load_icon(s[2])
		return None

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
		print "Status changed..."
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

	def add_contact_clicked(self, w):
		dlg = authorization_request(self.glade.window1, self.mrim, self.contact_list)

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
		M = self.glade.contacts.get_model()

		while True:
			iter = M.get_iter_first()
			if not iter:
				break
			M.remove(iter)

		for g in groups:
			giter = M.append(None)
			cl = [c for c in self.contact_list.list_contacts(groups.index(g))]
			M.set(giter, 1, "%s (%d)" % (g['name'], len(cl)))

			for c in cl:
				iter = M.append(giter)
				M.set(iter, 0, self._status_to_icon(c['status']), 1, c['address'])

	def message_received(self, msg):
		# TODO: show alert instead message "
		self.msg_wnd.show()
		self.msg_wnd.add_message(msg, direction = 'S2C')
		msg.submit()

	def authorization_received(self, msg):
		print "Authorization received..."
		w = authorization_window(self.glade.window1, msg)

	def message_status(self, status):
		if status == mrim.MESSAGE_DELIVERED:
			return

		s = 'Generic error'
		if status == mrim.MESSAGE_REJECTED_INTERR:
			s = 'Message rejected. Internal server error'
		elif status == mrim.MESSAGE_REJECTED_NOUSER:
			s = 'Message rejected. No specified user found.'
		elif status == mrim.MESSAGE_REJECTED_LIMIT_EXCEEDED:
			s = 'Message rejected. You message limit exceeded'
		elif status == mrim.MESSAGE_REJECTED_TOO_LARGE:
			s = 'Message rejected. Message too large'
		elif status == mrim.MESSAGE_REJECTED_DENY_OFFMSG:
			s = 'Message rejected. User denied offline messages'

		ErrorMessage(self.glade.window1, s)


if __name__ == '__main__':
	wnd = main_window()
	gtk.main()

