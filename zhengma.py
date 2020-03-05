#!usr/bin/env python
# -*- coding:utf-8 -*-

import Tkinter as tk
import ttk
import tkMessageBox


class ZhengMa:
    DATABASE = '/Users/xiaodong/Library/Application Support/OpenVanilla/UserData/TableBased/zhengma.cin'

    def __init__(self):
        self._words = []
        self.load_data_()

    def query(self, keyword):
        return (i for i in self._words if i.find(keyword) > -1)

    def load_data_(self):
        with open(ZhengMa.DATABASE, mode='r') as f:
            words = []
            head_passed = False
            for i in f:
                if head_passed:
                    if i.find('%chardef end') == -1:
                        words.append(i.decode('utf-8'))
                elif i.find('%chardef begin') > -1:
                    head_passed = True
        self._words = words

    def insert_new(self, code, word):
        last = '%chardef end\n'
        with open(ZhengMa.DATABASE, mode='r+') as f:
            f.seek(-len(last), 2)
            entry = u'%s %s\n' % (code, word)
            f.write(entry.encode('utf-8'))
            f.write(last)
            self._words.append(entry)

    @property
    def valid(self):
        return len(self._words) > 0


class BusyIndicator(tk.Toplevel):
    def __init__(self, master, *a, **kw):
        tk.Toplevel.__init__(self, master, *a, **kw)
        self.wm_overrideredirect(True)  # remove window title bar
        self.geometry("+%d+%d" % (master.winfo_rootx()+50,
                                  master.winfo_rooty()+50))
        canvas = tk.Canvas(self)
        canvas.pack(fill=tk.BOTH, expand=tk.YES)
        bmp = canvas.create_bitmap(0, 0, anchor=tk.NW, bitmap='hourglass')
        canvas.scale(bmp, 0, 0, 2, 2)
        box = canvas.bbox(tk.ALL)
        canvas.config(scrollregion=box, width=box[2], height=box[3])
        canvas.bind('<Map>', self.min_size_)
        # make it modal
        self.transient(master)  # if master minimize, it follows.
        self.lift()             # move to top
        self.focus_force()      # get input focus
        self.grab_set()         # handle all events itself

    def close(self):
        self.destroy()

    def min_size_(self, evt):
        """
        @note automatically called to decide the min size of top-level dialog
        """
        w, h = self.geometry().split('x')
        h = h[:h.index('+')]
        self.minsize(w, h)


class EntryOps:
    @staticmethod
    def select_all(evt):
        w = evt.widget
        if not isinstance(w, tk.Entry):
            return
        w.select_range(0, tk.END)

    @staticmethod
    def jump_to_start(evt):
        w = evt.widget
        if not isinstance(w, tk.Entry):
            return
        w.icursor(0)

    @staticmethod
    def jump_to_end(evt):
        w = evt.widget
        if not isinstance(w, tk.Entry):
            return
        w.icursor(tk.END)

    @staticmethod
    def copy(evt):
        w = evt.widget
        if not isinstance(w, tk.Entry):
            return
        w.event_generate('<<Copy>>')

    @staticmethod
    def cut(evt):
        w = evt.widget
        if not isinstance(w, tk.Entry):
            return
        w.event_generate('<<Cut>>')

    @staticmethod
    def paste(evt):
        w = evt.widget
        if not isinstance(w, tk.Entry):
            return
        w.event_generate('<<Paste>>')


class MainWnd(tk.Tk):
    """
    A utility to help edit zheng-ma file of OpenVanilla.
    """
    def __init__(self, *a, **kw):
        tk.Tk.__init__(self, *a, **kw)
        self.title('OpenVanilla Zheng-Ma Sprite')
        #
        frm = tk.Frame(self)
        # fill=X, expand=NO: fill horizontal space even when resizing window
        frm.pack(side=tk.TOP, fill=tk.X, expand=tk.NO, padx=5, pady=5)
        tk.Label(frm, text='Keyword:').pack(side=tk.LEFT)
        self._keyword = tk.StringVar()
        e = tk.Entry(frm, textvariable=self._keyword)
        e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        e.bind('<Return>', lambda evt: self.on_query_())
        self._btn = tk.Button(frm, text='Query', command=self.on_query_)
        self._btn.pack(side=tk.LEFT)
        #
        frm = tk.Frame(self)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        tree = ttk.Treeview(frm, show='headings', columns=('Code', 'Word'))
        tree.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.BOTH, expand=tk.YES)
        sclb = tk.Scrollbar(frm, orient=tk.VERTICAL, command=tree.yview)
        tree.config(yscrollcommand=sclb.set)
        sclb.pack(side=tk.RIGHT, fill=tk.Y, expand=tk.NO)
        tree.heading('#1', text='码')
        tree.heading('#2', text='字')
        #
        frm = tk.LabelFrame(self, text='Insert New Word')
        frm.pack(side=tk.TOP, fill=tk.X, expand=tk.NO, padx=5, pady=5)
        self._new_code = tk.StringVar()
        self._new_word = tk.StringVar()
        tk.Entry(frm, textvariable=self._new_code)\
            .pack(side=tk.LEFT, padx=5, pady=5)
        tk.Entry(frm, textvariable=self._new_word)\
            .pack(side=tk.LEFT, fill=tk.X, expand=tk.YES, padx=5, pady=5)
        tk.Button(frm, text='Insert', command=self.insert_new_word_)\
            .pack(side=tk.LEFT)
        self._words = tree
        self._database = ZhengMa()
        #
        self.bind('<Escape>', lambda evt: self.destroy())
        self.enhance_functions()

    def on_query_(self):
        if not self._database.valid:
            tkMessageBox.showinfo('ZhengMa', 'DataBase is empty!')
            return
        keyword = self._keyword.get().strip(' ')
        if keyword is '':
            return
        busy = BusyIndicator(self)
        # delete old
        self._words.delete(*self._words.get_children())
        # insert new
        for i in self._database.query(keyword):
            self._words.insert('', tk.END, values=i.split(' ', 2))
        if len(self._words.get_children('')) == 0:
            self._words.insert('', tk.END, values=('<Empty>', '<Empty>'))
        busy.close()
        # although indicator is destroyed, the focus doesn't go back. It vanishes!
        self.focus_force()

    def insert_new_word_(self):
        new_code = self._new_code.get().strip(' ')
        new_word = self._new_word.get().strip(' ')
        if not new_code.encode('utf8').isalpha():
            return
        if len(new_code) > 5:
            return
        if new_word is '':
            return
        new_code = new_code.lower()
        self._database.insert_new(new_code, new_word)
        # as a feedback, insert new word to QUERY window
        children = self._words.get_children('')
        if len(children) == 1 and self._words.item(children[0], 'values')[0] == '<Empty>':
            self._words.delete(*children)
        self._words.insert('', tk.END, values=(new_code, new_word))

    def enhance_functions(self):
        self.bind_class('Entry', '<Mod1-a>', EntryOps.select_all)
        self.bind_class('Entry', '<Mod1-A>', EntryOps.select_all)
        self.bind_class('Entry', '<Mod1-Left>', EntryOps.jump_to_start)
        self.bind_class('Entry', '<Mod1-Right>', EntryOps.jump_to_end)
        self.bind_class('Entry', '<Mod1-C>', EntryOps.copy)
        self.bind_class('Entry', '<Mod1-X>', EntryOps.cut)
        self.bind_class('Entry', '<Mod1-V>', EntryOps.paste)

if __name__ == '__main__':
    MainWnd().mainloop()
