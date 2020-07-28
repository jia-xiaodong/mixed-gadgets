#!usr/bin/env python
# -*- coding:utf-8 -*-

import Tkinter as tk
import ttk
import tkMessageBox
from os import SEEK_SET, SEEK_END

'''
郑码字库是一个UTF-8格式的文本文件，其内容按先后顺序分为下列几部分：
    注释区：这部分内容就是几行注释，估计不会有其它的作用。
    %keyname begin：与下面的keyname end共同构成“键区”。
    %keyname end：“键区”的内容我现在不需要理会。
    %chardef begin：与下面的chardef end构成了正式的字库区。
    %chardef end：字库区是我最需要关心的。
'''

class ZhengMa:
    DATABASE = '/Users/xiaodong/Library/Application Support/OpenVanilla/UserData/TableBased/zhengma.cin'

    def __init__(self):
        self._char_def = []
        self._start_pos = 0
        self.load_data_()

    def query(self, keyword):
        hit = []
        for index, char in enumerate(self._char_def):
            if char.find(keyword) > -1:
                hit.append((index, char))
        return hit

    def load_data_(self):
        AREA_COMMENT = 0
        AREA_KEYNAME_BEGIN = 1
        AREA_KEYNAME_END = 2
        AREA_CHARDEF = 3
        current_area = AREA_COMMENT
        ifo = open(ZhengMa.DATABASE, mode='r')
        pos = 0
        for line in ifo:  # Note: line contains "\n" at the end.
            pos += len(line)
            if current_area == AREA_CHARDEF:
                line = line.decode('utf-8')
                if line.startswith('%chardef end'):  # end of the whole file
                    break
                self._char_def.append(line)
            elif current_area == AREA_KEYNAME_END:
                if line.startswith('%chardef begin'):
                    current_area = AREA_CHARDEF
                    self._start_pos = pos
            elif current_area == AREA_KEYNAME_BEGIN:
                if line.startswith('%keyname end'):
                    current_area = AREA_KEYNAME_END
            else:  # AREA_COMMENT
                if line.startswith('%keyname begin'):
                    current_area = AREA_KEYNAME_BEGIN
        ifo.close()

    def save_data(self, removed_lines, inserted_lines):
        """
        @param removed_lines: an array of line numbers. range: [0, n)
        @param inserted_lines: an array of new words.
        """
        if len(removed_lines) > 0:
            ofo = open(ZhengMa.DATABASE, mode='r+')  # update-mode
            removed_lines.sort()  # in-place sort in ascending order
            #----------------------------------------------------------
            # prepare a new array which contains inserted lines and filters out the removed.
            first_removed = removed_lines[0]
            modified_words = []
            i = first_removed+1
            for j in removed_lines[1:]:
                modified_words.extend(self._char_def[i:j])
                i = j+1
            modified_words.extend(self._char_def[i:])
            modified_words.extend(['%s\n' % j for j in inserted_lines])
            #----------------------------------------------------------
            #
            offset = reduce(lambda s, i: s+len(self._char_def[i].encode('utf8')), range(0, first_removed), self._start_pos)
            ofo.seek(offset, SEEK_SET)  # skip the preceding part. no need to re-write them.
            ofo.writelines(i.encode('utf8') for i in modified_words)
            ofo.write('%chardef end\n')
            ofo.truncate()
            ofo.close()
            self._char_def[first_removed:] = modified_words  # release old strings
        else:
            last = '%chardef end\n'
            new_lines = ['%s\n' % i for i in inserted_lines]
            ofo = open(ZhengMa.DATABASE, mode='r+')
            ofo.seek(-len(last), SEEK_END)
            ofo.writelines(i.encode('utf8') for i in new_lines)
            ofo.write(last)
            ofo.close()
            self._char_def.extend(new_lines)

    @property
    def valid(self):
        return len(self._char_def) > 0


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


class TabBarFrame(tk.Frame):
    def __init__(self, master=None, *a, **kw):
        tk.Frame.__init__(self, master, *a, **kw)
        self.tabs = {}
        self.active = None
        self.top = tk.Frame(self)
        self.top.pack(side=tk.TOP, anchor=tk.W)

    def add(self, frame, caption):
        """
        @param frame is an instance of tk.Frame class
        """
        frame.pack_forget()  # hide on init
        btn = tk.Button(self.top, text=caption, relief=tk.SUNKEN,
                        foreground='white', disabledforeground='black', bg='grey',
                        command=(lambda: self.switch_tab(frame)))
        btn.pack(side=tk.LEFT)
        self.tabs[frame] = btn
        if len(self.tabs) == 1:
            self.switch_tab(frame)

    def remove(self, frame=None, caption=None):
        """
        @param frame is tk.Frame instance
        @param caption is str instance
        """
        if caption is not None:
            for f, t in self.tabs:
                if t['text'] == caption:
                    frame = f
                    break  # remove the first-found one even if multiple pages have same caption
        if frame is None:
            return
        if frame not in self.tabs:
            return
        frame.pack_forget()
        self.tabs[frame].pack_forget()
        del self.tabs[frame]
        if frame == self.active:
            self.active = None
            self.switch_tab()

    def switch_tab(self, frame=None):
        """
        @param frame is tk.Frame instance
        """
        if frame is None and len(self.tabs) > 0:
            frame = self.tabs.keys()[-1]
        if frame not in self.tabs:
            return
        if self.active:
            self.tabs[self.active].config(relief=tk.SUNKEN, state=tk.NORMAL)
            self.active.pack_forget()
        frame.pack(side=tk.BOTTOM, expand=tk.YES, fill=tk.BOTH)
        self.tabs[frame].config(relief=tk.FLAT, state=tk.DISABLED)
        self.active = frame


class QueryWord(tk.Frame):
    def __init__(self, master, *a, **kw):
        tk.Frame.__init__(self, master, *a, **kw)
        frm = tk.Frame(self)
        # fill=X, expand=NO: fill horizontal space even when resizing window
        frm.pack(side=tk.TOP, fill=tk.X, expand=tk.NO, padx=5, pady=5)
        tk.Label(frm, text='Keyword:').pack(side=tk.LEFT)
        self._keyword = tk.StringVar()
        e = tk.Entry(frm, textvariable=self._keyword)
        e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        self._btn = tk.Button(frm, text='Query', command=master.master.on_query_)
        self._btn.pack(side=tk.LEFT)
        #
        frm = tk.Frame(self)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        tree = ttk.Treeview(frm, show='headings', columns=('code', 'word', 'index'), displaycolumns=(0,1))
        tree.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.BOTH, expand=tk.YES)
        sclb = tk.Scrollbar(frm, orient=tk.VERTICAL, command=tree.yview)
        tree.config(yscrollcommand=sclb.set)
        sclb.pack(side=tk.RIGHT, fill=tk.Y, expand=tk.NO)
        tree.heading('#1', text='码')
        tree.heading('#2', text='字')
        tree.column('#1', width=150)
        tree.bind('<Key-Delete>', self.on_tree_delete_)
        self._words = tree

    def get_keyword(self):
        return self._keyword.get().strip(' ')

    def clear_table(self):
        self._words.delete(*self._words.get_children())

    def set_table(self, values):
        if len(values) == 0:
            self._words.insert('', tk.END, values=('<Empty>', '<Empty>'))
            return
        for index, char in values:
            code, word = char.split(' ', 2)
            self._words.insert('', tk.END, values=(code, word, index))

    def on_tree_delete_(self, evt):
        selected = self._words.selection()
        num = len(selected)
        if num == 0:
            return
        msg = 'Are you sure to delete %d words?' % num
        if not tkMessageBox.askokcancel('ZhengMa', msg):
            return
        words = []
        for iid in selected:
            c, w, i = self._words.item(iid, 'values')
            words.append((c,w,i))
        self.master.master.move_to_trash(words)
        self._words.delete(*selected)


class InsertWord(tk.Frame):
    def __init__(self, master, *a, **kw):
        tk.Frame.__init__(self, master, *a, **kw)
        frm = tk.Frame(self)
        frm.pack(side=tk.TOP, fill=tk.X, expand=tk.NO, padx=5, pady=5)
        self._new_code = tk.StringVar()
        self._new_word = tk.StringVar()
        tk.Entry(frm, textvariable=self._new_code, width=12).pack(side=tk.LEFT)
        tk.Entry(frm, textvariable=self._new_word).pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        tk.Button(frm, text='Insert', command=self.insert_new_word)\
            .pack(side=tk.LEFT)
        #
        frm = tk.Frame(self)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        tree = ttk.Treeview(frm, show='headings', columns=('Code', 'Word'))
        tree.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.BOTH, expand=tk.YES)
        sclb = tk.Scrollbar(frm, orient=tk.VERTICAL, command=tree.yview)
        tree.config(yscrollcommand=sclb.set)
        sclb.pack(side=tk.RIGHT, fill=tk.Y, expand=tk.NO)
        tree.heading('#1', text='码')
        tree.heading('#2', text='字')
        tree.column('#1', width=150)
        self._words = tree

    def insert_new_word(self):
        new_code = self._new_code.get().strip(' ')
        new_word = self._new_word.get().strip(' ')
        if not new_code.encode('utf8').isalpha():
            return
        if len(new_code) > 5:  # OpenVanilla support 5 keys at the most.
            return
        if new_word is '':
            return
        new_code = new_code.lower()
        # check duplicate
        value = '%s %s' % (new_code, new_word)
        if not value in self.get_values():
            self._words.insert('', tk.END, values=(new_code, new_word))

    def get_values(self):
        children = self._words.get_children('')
        values = [self._words.item(i, 'values') for i in children]
        return ['%s %s' % (i[0], i[1]) for i in values]

    def clear_table(self):
        self._words.delete(*self._words.get_children())


class RemoveWord(tk.Frame):
    def __init__(self, master, *a, **kw):
        tk.Frame.__init__(self, master, *a, **kw)
        frm = tk.Frame(self)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        tree = ttk.Treeview(frm, show='headings', columns=('code', 'word', 'index'), displaycolumns=(0,1))
        tree.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.BOTH, expand=tk.YES)
        sclb = tk.Scrollbar(frm, orient=tk.VERTICAL, command=tree.yview)
        tree.config(yscrollcommand=sclb.set)
        sclb.pack(side=tk.RIGHT, fill=tk.Y, expand=tk.NO)
        tree.heading('#1', text='码')
        tree.heading('#2', text='字')
        tree.column('#1', width=150)
        tree.bind('<Key-Delete>', self.on_tree_delete_)
        self._words = tree

    def set_table(self, values):
        children = self._words.get_children('')
        old_values = [self._words.item(iid, 'values') for iid in children]
        for code, word, index in values:
            new_value = (code, word, index)
            if not new_value in old_values:  # check duplicate
                self._words.insert('', tk.END, values=new_value)

    def on_tree_delete_(self, evt):
        selected = self._words.selection()
        self._words.delete(*selected)

    def get_values(self):
        word_indices = []
        children = self._words.get_children('')
        for iid in children:
            _, _, index = self._words.item(iid, 'values')
            word_indices.append(int(index))
        return word_indices

    def clear_table(self):
        self._words.delete(*self._words.get_children())


class MainWnd(tk.Tk):
    """
    A utility to help edit zheng-ma file of OpenVanilla.
    """
    def __init__(self, *a, **kw):
        tk.Tk.__init__(self, *a, **kw)
        self.title('OpenVanilla Zheng-Ma Sprite')
        #
        frm = TabBarFrame(self)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self._querier = QueryWord(frm)
        frm.add(self._querier, 'Query')
        self._inserter = InsertWord(frm)
        frm.add(self._inserter, 'Insert New')
        self._remover = RemoveWord(frm)
        frm.add(self._remover, 'To be Removed')
        self._tabbar = frm
        #
        self.bind('<Return>', lambda evt: self.default_button())
        self.bind('<Escape>', lambda evt: self.destroy())
        self.enhance_functions()
        #
        frm = tk.Frame(self)
        frm.pack(side=tk.TOP, fill=tk.X, expand=tk.NO, padx=5, pady=5)
        tk.Button(frm, text='Save Database', command=self.save_database)\
            .pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        tk.Button(frm, text='About', command=self.about_info)\
            .pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        #
        self._database = ZhengMa()

    def save_database(self):
        trash_indices = self._remover.get_values()
        newbie_values = self._inserter.get_values()
        self._database.save_data(trash_indices, newbie_values)
        self._remover.clear_table()
        self._inserter.clear_table()

    def about_info(self):
        tkMessageBox.showinfo('ZhengMa', '''
My char definition file of Zhengma for OpenVanilla is exported from \
some online vocabulary builder. So it has many, many words that I \
don't need.
That's why I finally made decision to spend one day making this widget \
out to fasten the word-removing operation. I don't need to launch vim \
again and again.
As for the new word insertion, it was done so long before that I can't \
remember the exact date.\n
Author: Tom Jay.
2020-7-28.
        ''')

    def on_query_(self):
        if not self._database.valid:
            tkMessageBox.showinfo('ZhengMa', 'DataBase is empty!')
            return
        keyword = self._querier.get_keyword()
        if keyword is '':
            return
        busy = BusyIndicator(self)
        self._querier.clear_table()
        self._querier.set_table(self._database.query(keyword))
        busy.close()
        # although indicator is destroyed, the focus doesn't go back. It vanishes!
        self.focus_force()

    def move_to_trash(self, values):
        self._remover.set_table(values)

    def default_button(self):
        if self._tabbar.active == self._querier:
            self.on_query_()
        elif self._tabbar.active == self._inserter:
            self._inserter.insert_new_word()

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
    #test()
