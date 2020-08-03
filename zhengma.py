#!usr/bin/env python
# -*- coding:utf-8 -*-

import Tkinter as tk
import ttk
import tkMessageBox
import tkFont
from os import SEEK_SET, SEEK_END

def entry_add_hint(entry, hint):
    """
    add a hint text (as placeholder) to an entry widget
    @param hint must be UNICODE string.
    """
    def on_focus_in(evt=None):
        if entry.get() == hint:
            entry.delete(0, tk.END)
    def on_focus_out(evt=None):
        if len(entry.get()) == 0:
            entry.insert(0, hint)
    entry.bind('<FocusIn>', on_focus_in)
    entry.bind('<FocusOut>', on_focus_out)
    on_focus_out()  # force to add hint


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


class TabBarTab:
    def __init__(self, caption, frame, has_close_button=False):
        self.caption = caption  # text of caption
        self.caption_id = 0     # text id in canvas. "0" means invalid id.
        self.shape_id = 0       # shape id in canvas. Shape can be rectangle or polygon.
        self.frame = frame
        # you can enable this feature
        self.close_btn = 0 if has_close_button else -1

    def has_close_button(self):
        return self.close_btn != -1

    def need_button(self):
        return self.close_btn == 0


class TabBarFrame(tk.Frame):
    BAR_H = 30         # width of whole tab-bar
    TAB_W = 120        # width of tab-button
    TAB_H = BAR_H - 8  # height of tab-button. "8" is a magic number.
    CLOSE_W = 25       # width fo "close" button
    MARGIN = 3         # margin to borders
    FOOTER_H = 7       # height of white ribbon at bottom
    PADDING = 8        # left/right padding for "X" (close button)s
    text_font = None

    def __init__(self, master=None, *a, **kw):
        tk.Frame.__init__(self, master, *a, **kw)
        self.tabs = []
        self.active = None
        self.top = tk.Canvas(self, height=TabBarFrame.BAR_H)
        self.top.pack(side=tk.TOP, anchor=tk.W, fill=tk.BOTH, expand=tk.YES)
        self.top.bind('<ButtonPress-1>', self.on_clicked)
        #
        if TabBarFrame.text_font is None:
            TabBarFrame.text_font = tkFont.Font()
        #
        self.bind('<Map>', self.on_widget_placed)        # event: widget placement
        self.bind('<Configure>', self.on_resize)  # event: resize

    def on_widget_placed(self, evt):
        self.switch_tab(self.active)

    def on_resize(self, evt):
        current_active_frame = self.active
        self.active = None  # clear it to force redrawing of active tab
        self.switch_tab(current_active_frame)

    def add(self, frame, caption):
        """
        @param frame is an instance of tk.Frame class
        """
        frame.pack_forget()  # hide on init
        self.tabs.append(TabBarTab(caption, frame))
        if len(self.tabs) == 1:
            self.event_generate('<Map>')
        else:
            self.draw_tab(len(self.tabs)-1, False)

    def remove(self, frame):
        """
        @param frame is tk.Frame instance
        @param caption is str instance
        """
        index = self.tab_index_by_frame(frame)
        #
        for i, t in enumerate(self.tabs[index+1:]):
            if t.frame == self.active:
                self.draw_tab(i, True)
            else:
                self.top.move(t.shape_id, -TabBarFrame.TAB_W, 0)
                self.top.move(t.caption_id, -TabBarFrame.TAB_W, 0)
                self.top.move(t.close_btn, -TabBarFrame.TAB_W, 0)
        #
        tab = self.tabs[index]
        self.top.delete(tab.caption_id, tab.shape_id, tab.close_btn)
        self.tabs.remove(tab)
        frame.pack_forget()
        #
        if frame == self.active:
            self.active = None
            self.switch_tab()

    def tab_index_by_frame(self, frame):
        for i, t in enumerate(self.tabs):
            if t.frame == frame:
                return i
        raise Exception("The specified frame doesn't exist.")

    def switch_tab(self, frame=None):
        """
        @param frame is tk.Frame instance
        """
        if frame is None:
            if len(self.tabs) > 0:
                frame = self.tabs[-1].frame
            else:
                return

        # draw previous active as grey rectangle
        if self.active:
            if self.active == frame:
                return
            index = self.tab_index_by_frame(self.active)
            self.draw_tab(index, False)
            self.active.pack_forget()
        frame.pack(side=tk.BOTTOM, expand=tk.YES, fill=tk.BOTH)
        self.active = frame
        # draw current active as white button
        index = self.tab_index_by_frame(frame)
        self.draw_tab(index, True)

    def on_clicked(self, evt):
        clicked = self.top.find_closest(evt.x, evt.y)
        for t in self.tabs:
            shapes = [t.caption_id, t.shape_id]
            if any(i in shapes for i in clicked):
                return self.switch_tab(t.frame)

    def draw_tab(self, index, is_active):
        # draw shape
        tab = self.tabs[index]
        self.top.delete(tab.shape_id)  # delete old shape
        if is_active:
            # create new shape
            if index == 0:
                x0 = TabBarFrame.MARGIN
                y0 = TabBarFrame.MARGIN
                points = [(x0, y0)]      # point 1 (top-left corner)
                x0 += TabBarFrame.TAB_W
                points.append((x0, y0))  # point 2
                y0 += TabBarFrame.TAB_H
                points.append((x0, y0))  # point 3
                x0 = self.winfo_width() - TabBarFrame.MARGIN - 1  # can't be used in __init__()
                points.append((x0, y0))  # point 4
                y0 += TabBarFrame.FOOTER_H
                points.append((x0, y0))  # point 5
                x0 = TabBarFrame.MARGIN
                points.append((x0, y0))  # point 6
                tab.shape_id = self.top.create_polygon(*points, outline='black', fill='')
            else:
                x0 = TabBarFrame.MARGIN + index * TabBarFrame.TAB_W
                y0 = TabBarFrame.MARGIN
                points = [(x0, y0)]      # point 1 (top-left corner)
                x0 += TabBarFrame.TAB_W
                points.append((x0, y0))  # point 2
                y0 += TabBarFrame.TAB_H
                points.append((x0, y0))  # point
                x0 = self.winfo_width() - TabBarFrame.MARGIN - 1
                points.append((x0, y0))  # point
                y0 += TabBarFrame.FOOTER_H
                points.append((x0, y0))  # point
                x0 = TabBarFrame.MARGIN
                points.append((x0, y0))  # point
                y0 -= TabBarFrame.FOOTER_H
                points.append((x0, y0))  # point
                x0 = TabBarFrame.MARGIN + index * TabBarFrame.TAB_W
                points.append((x0, y0))  # point
                tab.shape_id = self.top.create_polygon(*points, outline='black', fill='')
        else:
            x0 = TabBarFrame.MARGIN + index * TabBarFrame.TAB_W
            y0 = TabBarFrame.MARGIN
            x1 = x0 + TabBarFrame.TAB_W
            y1 = y0 + TabBarFrame.TAB_H
            tab.shape_id = self.top.create_rectangle(x0, y0, x1, y1, fill='grey')
        # draw text
        if tab.caption_id == 0:
            btn_width = TabBarFrame.TAB_W - TabBarFrame.PADDING * 2
            if tab.has_close_button():
                btn_width -= TabBarFrame.CLOSE_W
            req_width = TabBarFrame.text_font.measure(tab.caption)
            x = TabBarFrame.MARGIN + index * TabBarFrame.TAB_W
            y = TabBarFrame.MARGIN
            center_pos = (x+btn_width/2+TabBarFrame.PADDING, y+TabBarFrame.TAB_H/2)
            if req_width > btn_width:
                caption = '%s...' % self.sub_str_by_width(tab.caption, btn_width)
                tab.caption_id = self.top.create_text(*center_pos, text=caption)
                self.enable_tip(tab)
            else:
                tab.caption_id = self.top.create_text(*center_pos, text=tab.caption)
        else:
            self.top.tag_lower(tab.shape_id, tab.caption_id)
        # draw close button
        if tab.need_button():
            x = TabBarFrame.MARGIN + (index+1) * TabBarFrame.TAB_W
            y = TabBarFrame.MARGIN
            center_pos = (x-TabBarFrame.CLOSE_W/2, y+TabBarFrame.TAB_H/2)
            tab.close_btn = self.top.create_text(*center_pos, text='X')
            self.top.tag_bind(tab.close_btn, '<ButtonPress>', lambda e: self.remove(tab.frame))

    def sub_str_by_width(self, text, width):
        width -= self.text_font.measure('...')  # subtract "..." in advance
        for i in range(len(text), 0, -1):
            w = self.text_font.measure(text[:i])
            if width > w:
                return text[:i]
        return ''

    def enable_tip(self, tab):
        self.tip_wnd = None
        def show_tip(evt):
            self.tip_wnd = tk.Toplevel(self.top)
            self.tip_wnd.wm_overrideredirect(True)  # remove window title bar
            label = tk.Label(self.tip_wnd, text=tab.caption, justify=tk.LEFT)
            label.pack(ipadx=5)
            x, y = evt.x_root, evt.y_root
            w, h = label.winfo_reqwidth(), label.winfo_reqheight()
            sw, sh = label.winfo_screenwidth(), label.winfo_screenheight()
            offset = 20
            if x + w + offset > sw:  # if reach beyond the right border
                x -= w + offset*2    # place tip to the left of widget
            if y + h + offset > sh:  # if reach beyond the bottom border
                y -= h + offset*2    # place tip to the top of widget
            self.tip_wnd.wm_geometry("+%d+%d" % (x+offset, y+offset))
        def hide_tip(evt):
            if self.tip_wnd:
                self.tip_wnd.destroy()
        self.top.tag_bind(tab.caption_id, "<Enter>", show_tip)
        self.top.tag_bind(tab.caption_id, "<Leave>", hide_tip)


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
        entry_add_hint(e, u'<码或词>')
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
        e = tk.Entry(frm, textvariable=self._new_code, width=12)
        e.pack(side=tk.LEFT)
        entry_add_hint(e, u'<码>')
        e = tk.Entry(frm, textvariable=self._new_word)
        e.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        entry_add_hint(e, u'<词>')
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
        tree.bind('<Key-Delete>', self.on_tree_delete_)
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

    def on_tree_delete_(self, evt):
        selected = self._words.selection()
        self._words.delete(*selected)

    def clear_input(self):
        self._new_word.set('')
        self._new_code.set('')


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
        tk.Button(frm, text='Save to Database', command=self.save_database)\
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
        self._inserter.clear_input()

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
