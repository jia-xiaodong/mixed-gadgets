#!/usr/bin/python
# -*- coding: utf-8 -*-

import Tkinter as tk
import ttk
import tkFileDialog, tkMessageBox, tkFont
import sqlite3
import datetime
import zlib
import os, sys
import math


class KnowledgePoint():
    """
    A word is composed by various of knowledge points.
    For example, word 'class' can have below knowledge points:
    1. spelling: c-l-a-s-s
    2. pronunciation: [kla:s]
    3. common phrases: class act, first-class, class-conscious
    4. grammar: noun
    Accordingly, one knowledge point looks like a tuple: ('grammar', 'noun'), which is
    abstracted as form of (facet, value). And 'grammar' is facet, 'noun' is its value.
    """
    def __init__(self, facet, value):
        self.facet = facet
        self.value = value

    def to_str(self):
        return '%s %s%s' % (len(self.facet), self.facet, self.value)

    @classmethod
    def from_str(cls, s):
        """
        @param s: looks like '5 spellexpect', 5 is the length of 'spell'
        """
        try:
            digit_end = s.find(' ')          # 1
            digit_len = int(s[:digit_end])   # 5
            word_end = digit_len+digit_end+1 # 7
            facet = s[digit_end+1:word_end]  # s[2:7] -> spell
            value = s[word_end:]             # s[8]   -> expect
            return cls(facet, value)
        except Exception as e:
            print('Error: %s' % e)
            return None

    @staticmethod
    def array_to_str(points):
        """
        @param points: array of KnowledgePoint objects
        """
        intermediate = [i.to_str() for i in points]
        intermediate = ['%d %s' % (len(i), i) for i in intermediate]
        return ''.join(intermediate)

    @staticmethod
    def array_from_str(s):
        points = []
        try:
            word_end = 0
            digit_end = s.find(' ')
            while digit_end > -1:
                digit_len = int(s[word_end:digit_end])
                word_end = digit_end+digit_len+1
                word = s[digit_end+1:word_end]
                points.append(KnowledgePoint.from_str(word))
                digit_end = s.find(' ', word_end)
        except Exception as e:
            print('Error: %s' % e)
        finally:
            return points


class WordRecord():
    """
    Represents a row of record in database. So it communicates with database.
    """
    COL_ID   = 0  # INTEGER, as data index.
    COL_WORD = 1  # BLOB, where all knowledge points of one word are stored.
    COL_TURN = 2  # INTEGER, representing how many rounds you've reviewed this word.
    COL_DATE = 3  # DATE, when you reviewed this word recently.
    DATE_FORMAT = '%Y-%m-%d'  # 2019-03-18

    def __init__(self, knowledge_points, turn=None, date=None, sn=-1):
        """
        @param knowledge_points is array of KnowledgePoint objects.
        @param turn is how many rounds you've been reviewing this word.
        @param date is the time when this word is learned or reviewed recently.
        """
        self.points = knowledge_points
        self.turn = 0 if turn is None else turn
        self.date = datetime.date.today() if date is None else date
        self.sn = sn
        self.due_turn = None

    def zipped(self):
        s = KnowledgePoint.array_to_str(self.points)
        s = s.encode(encoding='utf-8')  # zlib accepts only str, not unicode str.
        return zlib.compress(s, 6)

    def mark_as_pass(self):
        """
        This word is passed-through, which is ready for the next turn of test.
        """
        try:
            interval = datetime.date.today() - self.date
            self.due_turn = int(math.log(interval.days, 2)) + 1
        except ValueError:
            print('record %d is just edited.' % self.sn)

    def mark_as_fail(self):
        """
        This word isn't get passed through, so mark it as a new word, which
        should be reviewed tomorrow.
        """
        self.due_turn = 0

    def mark_as_untested(self):
        self.due_turn = None

    @property
    def untested(self):
        return self.due_turn is None

    @property
    def passed(self):
        return self.due_turn is not None and self.due_turn > 0

    @classmethod
    def from_record(cls, row):
        s = zlib.decompress(row[WordRecord.COL_WORD])
        s = s.decode(encoding='utf-8')
        points = KnowledgePoint.array_from_str(s)
        return cls(points, row[WordRecord.COL_TURN], row[WordRecord.COL_DATE], row[WordRecord.COL_ID])


class WordStore():
    """
    Word store is what it's called: a database of words.
    The database can have many tables and they have the same monotonous structure
    of below four columns.
    """
    COL_0 = 'id'    # INTEGER, as data index.
    COL_1 = 'word'  # BLOB, where all knowledge points of one word are stored.
    COL_2 = 'turn'  # INTEGER, representing how many rounds you've reviewed this word.
    COL_3 = 'date'  # DATE, when you reviewed this word recently.

    def __init__(self, filename, table_name):
        self._con = sqlite3.connect(filename, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES)
        self._con.create_collation('OnDue', WordStore.collate_due_date)
        self._tbl = table_name

    def insert_word(self, word):
        """
        Insert a new word to database.
        @param word is WordRecord object.
        """
        try:
            cur = self._con.cursor()
            cur.execute('INSERT INTO %s(%s, %s, %s) VALUES(?,?,?)' %
                        (self._tbl, WordStore.COL_1, WordStore.COL_2, WordStore.COL_3),
                        (sqlite3.Binary(word.zipped()), word.turn, word.date))
            self._con.commit()
        except Exception as e:
            print('Error on insertion: %s' % e)

    def update_word(self, word):
        try:
            cur = self._con.cursor()
            sql = 'UPDATE %s SET word=? WHERE id=?' % self._tbl
            args = (sqlite3.Binary(word.zipped()), word.sn)
            cur.execute(sql, args)
            self._con.commit()
        except Exception as e:
            print('Error on update: %s' % e)

    def review_num(self, turn):
        """
        How many words am I supposed to review today?
        @param round: generally should be 1.
                      Value greater than 1 means you want to review a few words in advance.
        @return word number of you want to review.
        """
        class WordCounter():
            def __init__(self):
                self.count = 0
                self.today = datetime.date.today()

            def step(self, n, date):
                date = datetime.datetime.strptime(date, WordRecord.DATE_FORMAT)
                due = date.date() + datetime.timedelta(days=2**(n-turn+1))
                if self.today >= due:
                    self.count += 1

            def finalize(self):
                return self.count

        self._con.create_aggregate('WordCount', 2, WordCounter)
        cur = self._con.cursor()
        cur.execute('SELECT WordCount(turn, date) from %s' % self._tbl)
        count = cur.fetchone()
        return count

    def retrieve_today(self):
        words = []
        try:
            cur = self._con.cursor()
            today = datetime.date.today()
            cur.execute('SELECT id, word, turn FROM %s WHERE date=?' % self._tbl, (today,))
            for sn, word, turn in cur.fetchall():
                s = zlib.decompress(word)
                s = s.decode(encoding='utf-8')
                points = KnowledgePoint.array_from_str(s)
                words.append(WordRecord(points, turn, today, sn))
        except Exception as e:
            print('Error on selection: %s' % e)
        finally:
            return words

    def retrieve_due(self, turn):
        """
        Retrieve all words that is due to review.
        """
        def due_date(n, date):
            date = datetime.datetime.strptime(date, WordRecord.DATE_FORMAT)
            due = date.date() + datetime.timedelta(days=2**(n-turn+1))
            return due.strftime(WordRecord.DATE_FORMAT)
        try:
            self._con.create_function('DueDate', 2, due_date)
            cur = self._con.cursor()
            sql = '''SELECT *, DueDate(turn, date) AS due FROM %s
                        WHERE due<=?
                        ORDER BY due COLLATE OnDue''' % self._tbl
            cur.execute(sql, (datetime.date.today(),))
            words = [WordRecord.from_record(row) for row in cur]
            return words
        except Exception as e:
            print('Error on selection: %s' % e)
            return []

    def update_progress(self, changed_words):
        """
        @param changed_words: array of WordRecord objects.
        """
        try:
            today = datetime.date.today()
            cur = self._con.cursor()
            sql = 'UPDATE %s SET turn=?, date=? WHERE id=?' % self._tbl
            args = [(i.due_turn, today, i.sn) for i in changed_words]
            cur.executemany(sql, args)
            self._con.commit()
        except Exception as e:
            print('Error on update: %s' % e)

    @staticmethod
    def list_tables(filename):
        """
        @return None if this file isn't dedicated for Word-Pal, otherwise all table names.
        """
        def is_column_identical(cursor, table_name, table_columns):
            cursor.execute('PRAGMA table_info (%s)' % table_name)
            structs = cursor.fetchall()
            result = (structs[i][1] == table_columns[i] for i in range(len(table_columns)))
            return all(result)
        try:
            with sqlite3.connect(filename) as con:
                cur = con.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [i[0] for i in cur.fetchall()]
                column_names = [WordStore.COL_0, WordStore.COL_1, WordStore.COL_2, WordStore.COL_3]
                qualified = filter(lambda i: is_column_identical(cur, i, column_names), tables)
            #
            # [design] all tables have same structure. If not, this database is unknown.
            if len(qualified) != len(tables):
                return None
            return qualified
        except:
            return None

    @staticmethod
    def insert_table(filename, table_name):
        try:
            with sqlite3.connect(filename, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES) as con:
                con.execute('''
                    CREATE TABLE %s (
                        %s  INTEGER  PRIMARY KEY UNIQUE NOT NULL,
                        %s  BLOB     NOT NULL,
                        %s  INTEGER,
                        %s  DATE);''' % (table_name, WordStore.COL_0, WordStore.COL_1, WordStore.COL_2, WordStore.COL_3))
            return True
        except Exception as e:
            print('Error on creation of DB: %s' % e)
            return False

    @staticmethod
    def collate_due_date(date1, date2):
        """
        sort based on due date: the date earlier, the order first.
        """
        date1 = datetime.datetime.strptime(date1, WordRecord.DATE_FORMAT)
        date2 = datetime.datetime.strptime(date2, WordRecord.DATE_FORMAT)
        return -1 if date1 < date2 else 1 if date1 > date2 else 0

    def close(self):
        self._con.close()
        self._tbl = None

    @property
    def table(self):
        return self._tbl


class ModalDialog(tk.Toplevel):
    """
    modal dialog should inherit from this class and override:
    1. body(): required: place your widgets
    2. apply(): required: calculate returning value
    3. buttonbox(): optional: omit it if you like standard buttons (OK and cancel)
    4. validate(): optional: you may need to check if input is valid.

    Dialog support keyword argument: title=...
    Place your widgets on method body()
    Get return value from method apply()
    """
    def __init__(self, parent, *a, **kw):
        title = kw.pop('title') if 'title' in kw else None

        tk.Toplevel.__init__(self, parent, *a, **kw)
        self.transient(parent)  # when parent minimizes to an icon, it hides too.

        if title:  # dialog title
            self.title(title)

        self.parent = parent
        self.result = None

        body = tk.Frame(self)
        self.initial_focus = self.body(body)
        body.pack(padx=5, pady=5, expand=tk.YES, fill=tk.BOTH)
        body.bind('<Map>', self.min_size)
        self.buttonbox()

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.geometry("+%d+%d" % (parent.winfo_rootx()+50,
                                  parent.winfo_rooty()+50))

        if not self.initial_focus:
            self.initial_focus = self
        self.initial_focus.focus_set()

        self.lift()
        self.focus_force()
        self.grab_set()
        self.grab_release()

    def show(self):
        """
        enter a local event loop until dialog is destroyed.
        """
        self.wait_window(self)

    #
    # construction hooks

    def body(self, master):
        """
        Create dialog body.
        @param master: passed-in argument
        @return widget that should have initial focus.
        @note: must be overridden
        """
        return None

    def buttonbox(self):
        """
        Add standard button box (OK and cancel).
        @note: Override if you don't want the standard buttons
        """
        box = tk.Frame(self)

        w = tk.Button(box, text="OK", width=10, command=self.ok, default=tk.ACTIVE)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        w = tk.Button(box, text="Cancel", width=10, command=self.cancel)
        w.pack(side=tk.LEFT, padx=5, pady=5)

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

        box.pack()
        return box

    #
    # standard button semantics

    def ok(self, event=None):
        if not self.validate():
            if self.initial_focus:
                self.initial_focus.focus_set()
            return

        self.withdraw()
        self.update_idletasks()

        self.apply()
        self.cancel()

    def cancel(self, event=None):
        self.parent.focus_set()
        self.destroy()

    #
    # command hooks

    def validate(self):
        """
        @note: override if needed
        """
        return True

    def apply(self):
        """
        @note: must be overridden
        """
        pass

    def min_size(self, evt):
        """
        @note automatically called to decide the min size of top-level dialog
        """
        w, h = self.geometry().split('x')
        h = h[:h.index('+')]
        self.minsize(w, h)


class SpecifyWordStoreFrame(tk.Frame):
    def __init__(self, master, *a, **kw):
        tk.Frame.__init__(self, master, *a, **kw)
        frm = tk.LabelFrame(master, text='Step 1: Choose a File')
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        sub = tk.Frame(frm)
        sub.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        tk.Label(sub, text='Filename:').pack(side=tk.LEFT)
        self.filename = tk.StringVar()
        self.combo1 = ttk.Combobox(sub, textvariable=self.filename, state='readonly')  # disable keyboard input
        self.combo1.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        self.combo1.bind('<<ComboboxSelected>>', self.on_db_selected)
        sub = tk.Frame(frm)
        sub.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        tk.Button(sub, text='Browse Old', command=self.browse_old).pack(side=tk.LEFT)
        tk.Button(sub, text='Create New', command=self.create_new).pack(side=tk.RIGHT)
        frm = tk.LabelFrame(master, text='Step 2: Choose a Language')
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        tk.Label(frm, text='Language:').pack(side=tk.LEFT)
        self.table_name = tk.StringVar()
        self.combo2 = ttk.Combobox(frm, textvariable=self.table_name)
        self.combo2.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES, padx=5, pady=5)

    def browse_old(self):
        option = {'filetypes': [('SQLite3 File', ('*.db3', '*.s3db', '*.sqlite3', '*.sl3')),
                                ('All Files', ('*.*',))]}
        filename = tkFileDialog.askopenfilename(**option)
        if len(filename) == 0:
            return
        self.update_combo1(filename)

    def create_new(self):
        filename = tkFileDialog.asksaveasfilename(defaultextension='.sqlite3')
        if len(filename) == 0:
            return
        # My Design on Overwriting: do NOT overwrite!!
        if os.path.exists(filename):
            tkMessageBox.showerror('Word-Pal', "Cannot remove %s." % filename)
            return
        self.update_combo1(filename)

    def word_source(self):
        filename = self.filename.get()
        table = self.table_name.get()
        if filename == '':
            return None
        if table == '':
            return None
        if self.combo2.current() == -1:  # not found in combo's candidates
            if WordStore.insert_table(filename, table):
                history = list(self.combo2.cget('values'))
                history.append(filename)
                self.combo2.config(values=history)
            else:
                self.combo2.set('')
                tkMessageBox.showerror('Word-Pal', 'New table cannot be inserted.')
                return None
        return filename, table

    def update_combo1(self, filename):
        if not self.on_db_selected(filename):
            return
        self.combo1.set(filename)
        history = list(self.combo1.cget('values'))
        if filename not in history:
            history.append(filename)
        self.combo1.config(values=history)

    def on_db_selected(self, evt=None):
        try:
            filename = evt if isinstance(evt, basestring) else self.filename.get()
            if not os.path.exists(filename):
                raise IOError
            tables = WordStore.list_tables(filename)
            if tables is None:
                tkMessageBox.showerror('World-Pal', 'Wrong database file!')
                self.combo1.set('')
                raise TypeError
            self.combo2['values'] = tables
            if len(tables) > 0:
                self.combo2.current(0)  # first table as default
            else:
                self.combo2.set('')
            return True
        except Exception as e:
            self.combo2.config(values=[])
            self.combo2.set('')
            return True if type(e) is IOError else False


class EditWord(ModalDialog):
    MODE_INSERT = 0  # insert new word to database
    MODE_MODIFY = 1  # modify existent word

    class OneEntry():
        """
        Represents a knowledge point, which will be sent to KnowledgePoint object.
        A group of OneEntry will make up a complete WordRecord object.
        """
        def __init__(self):
            self.frame = None
            self.facet = tk.StringVar()
            self.value = None  # tk.Text object

        def get(self):
            f, v = self.facet.get(), self.value.get('1.0', tk.END)
            return f.strip(' \n'), v.strip(' \n')

    def __init__(self, parent, *a, **kw):
        self._db = kw.pop('source')
        self._word = kw.pop('word', None)
        self.entry_parent = None
        self.entries = []
        ModalDialog.__init__(self, parent, *a, **kw)
        self.bind('<Control-Return>', lambda evt: self.add_entry_below())

    def body(self, master):
        self.entry_parent = master
        if self.is_insert_mode():
            self.add_entry_below()
        else:
            for i, p in enumerate(self._word.points):
                self.add_entry_below()
                self.entries[i].facet.set(p.facet)
                self.entries[i].value.insert(tk.END, p.value)

    def add_entry_below(self):
        entry = EditWord.OneEntry()
        self.entries.append(entry)
        frm = tk.Frame(self.entry_parent)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self._pack_widget(entry, frm)

    def delete_entry(self, target_frm):
        for sn, entry in enumerate(self.entries):
            if entry.frame == target_frm:
                entry = self.entries.pop(sn)
                entry.frame.destroy()
                return

    def add_entry_above(self, frame):
        for sn, entry in enumerate(self.entries):
            if entry.frame == frame:
                break
        self.entries.insert(sn, EditWord.OneEntry())
        frm = tk.Frame(self.entry_parent)
        frm.pack(before=frame, side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self._pack_widget(self.entries[sn], frm)

    def _pack_widget(self, entry, frm):
        entry.frame = frm
        tk.Label(frm, text='type:').pack(side=tk.LEFT)
        types = ['spell', 'phonic', 'meaning', 'example', 'phrase', 'idiom', 'synonym', 'antonym']
        combo = ttk.Combobox(frm, textvariable=entry.facet, values=types, width=10)
        combo.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        tk.Label(frm, text='value:').pack(side=tk.LEFT)
        entry.value = tk.Text(frm, highlightbackground='gray', highlightthickness=1, width=20, height=1)
        entry.value.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES)
        entry.value.bind('<Return>', self.handle_return)
        tk.Button(frm, text='-1', command=lambda: self.delete_entry(frm), takefocus=0).pack(side=tk.LEFT)
        tk.Button(frm, text='+1 Above', command=lambda: self.add_entry_above(frm)).pack(side=tk.RIGHT)
        # focus to combo box
        combo.focus_set()
        self.enhance_combo(combo)

    def validate(self):
        for entry in self.entries:
            text1, text2 = entry.get()
            if text1 == '':
                return False
            if text2 == '':
                return False
        return True

    def apply(self):
        points = [KnowledgePoint(*i.get()) for i in self.entries]
        if self.is_insert_mode():
            self._db.insert_word(WordRecord(points))
        else:
            self._word.points[:] = points
            self._db.update_word(self._word)
            self.result = self._word  # 'MODIFY' mode need this result.

    def buttonbox(self):
        box = tk.Frame(self)
        box.pack()
        #
        options = {'side': tk.LEFT, 'padx': 5, 'pady': 5, 'expand': tk.YES, 'fill': tk.BOTH}
        w = tk.Button(box, text="+1 Below", command=self.add_entry_below, default=tk.ACTIVE)
        w.pack(**options)
        w = tk.Button(box, text="Write to Store", command=self.ok)
        w.pack(**options)
        w = tk.Button(box, text="Cancel", command=self.cancel)
        w.pack(**options)
        #
        self.bind("<Escape>", self.ok)

    def is_insert_mode(self):
        """
        INSERT mode or MODIFY mode?
        """
        return True if self._word is None else False

    def handle_return(self, evt):
        """
        Auto adjust size of tk.Text
        """
        if (evt.state & 0x0004) > 0:
            self.add_entry_below()
            return 'break'
        text = evt.widget
        line, _ = text.index(tk.END).split('.')
        text.config(height=int(line))

    def enhance_combo(self, w):
        if not isinstance(w, ttk.Combobox):
            return
        w.bind('<Mod1-a>', EntryOps.select_all)
        w.bind('<Mod1-A>', EntryOps.select_all)
        w.bind('<Mod1-Left>', EntryOps.jump_to_start)
        w.bind('<Mod1-Right>', EntryOps.jump_to_end)
        w.bind('<Mod1-C>', EntryOps.copy)
        w.bind('<Mod1-X>', EntryOps.cut)
        w.bind('<Mod1-V>', EntryOps.paste)


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


class TextOps:
    @staticmethod
    def select_all(evt):
        w = evt.widget
        if not isinstance(w, tk.Text):
            return
        w.tag_add(tk.SEL, '1.0', tk.END)

    @staticmethod
    def jump_to_start(evt):
        w = evt.widget
        if not isinstance(w, tk.Text):
            return
        curr = w.index(tk.INSERT)
        start = '%s linestart' % curr
        sel = w.tag_ranges(tk.SEL)
        if evt.state & 0x0001:  # shift pressed
            end = sel[1] if len(sel) else curr
            w.tag_add(tk.SEL, start, end)
        elif len(sel) > 0:
            w.tag_remove(tk.SEL, tk.SEL_FIRST, tk.SEL_LAST)
        #
        w.mark_set(tk.INSERT, start)  # move cursor to line start
        w.see(start)                  # scroll to line start
        return 'break'                # avoid the extra 'key handler'

    @staticmethod
    def jump_to_end(evt):
        w = evt.widget
        if not isinstance(w, tk.Text):
            return
        curr = w.index(tk.INSERT)
        end = '%s lineend' % curr
        sel = w.tag_ranges(tk.SEL)
        if evt.state & 0x0001:  # shift pressed
            start = sel[0] if len(sel) else curr
            w.tag_add(tk.SEL, start, end)
        elif len(sel) > 0:
            w.tag_remove(tk.SEL, tk.SEL_FIRST, tk.SEL_LAST)
        #
        w.mark_set(tk.INSERT, end)  # move cursor to line start
        w.see(end)                  # scroll to line start
        return 'break'              # avoid the extra 'key handler'

    @staticmethod
    def copy(evt):
        w = evt.widget
        if not isinstance(w, tk.Text):
            return
        w.event_generate('<<Copy>>')

    @staticmethod
    def cut(evt):
        w = evt.widget
        if not isinstance(w, tk.Text):
            return
        w.event_generate('<<Cut>>')

    @staticmethod
    def paste(evt):
        w = evt.widget
        if not isinstance(w, tk.Text):
            return
        w.event_generate('<<Paste>>')
    
    @staticmethod
    def jump_top(evt):
        w = evt.widget
        if not isinstance(w, tk.Text):
            return
        curr = w.index(tk.INSERT)
        sel = w.tag_ranges(tk.SEL)
        if evt.state & 0x0001:  # shift pressed
            end = sel[1] if len(sel) else curr
            w.tag_add(tk.SEL, '1.0', end)
        elif len(sel) > 0:
            w.tag_remove(tk.SEL, tk.SEL_FIRST, tk.SEL_LAST)
        #
        w.mark_set(tk.INSERT, '1.0')  # move cursor to top
        w.see('1.0')                  # scroll to top
        return 'break'                # avoid the extra 'key handler'

    @staticmethod
    def jump_bottom(evt):
        w = evt.widget
        if not isinstance(w, tk.Text):
            return
        curr = w.index(tk.INSERT)
        sel = w.tag_ranges(tk.SEL)
        if evt.state & 0x0001:  # shift pressed
            start = sel[0] if len(sel) else curr
            w.tag_add(tk.SEL, start, tk.END)
        elif len(sel) > 0:
            w.tag_remove(tk.SEL, tk.SEL_FIRST, tk.SEL_LAST)
        #
        w.mark_set(tk.INSERT, tk.END)  # move cursor to bottom
        w.see(tk.END)                  # scroll to bottom
        return 'break'                 # avoid the extra 'key handler'


class ReciteWord(ModalDialog):
    """
    Now I decide to review words based on below day-interval:
        1, 3, 7, 15, 31, 63, 127, ...
    It means:
    1: The first review should be started at the second day,
    2: The second review starts at the 3rd day,
    3: The 3rd review starts at the 7th day,
    and etc.
    So it's a simple formula: 2^n - 1, n is the nth round of review.
    """
    MODE_TEST = 0   # test all due words
    MODE_TODAY = 1  # view today's words
    SCROLL_STEP = -1 if sys.platform == 'darwin' else -120
    DEFAULT_FONT = 'Helvetica' if sys.platform == 'darwin' else 'Courier'
    FONT_HEIGHT = 0
    LINE_SPACE = 0

    def __init__(self, parent, *a, **kw):
        self._db = kw.pop('source')
        self.canvas = None
        self.font_family = tk.StringVar(value=ReciteWord.DEFAULT_FONT)
        self.font_size = tk.StringVar(value=18)
        self.font = tkFont.Font(family=ReciteWord.DEFAULT_FONT, size=18)
        ReciteWord.FONT_HEIGHT = self.font.metrics('linespace')
        ReciteWord.LINE_SPACE = ReciteWord.FONT_HEIGHT / 3
        self.title_base = kw['title']
        self.move_param = (0, 0, 0, 0)
        self.moved_objs = None
        self.mode = ReciteWord.MODE_TEST if 'turn' in kw else ReciteWord.MODE_TODAY
        self.switch_hide = tk.IntVar(value=1)  # 0: show all; 1: show untested
        self.switch_label = tk.StringVar(value=u'\u2639')
        #
        self.words = self.load_words(kw.pop('turn', None))  # 'turn' is synonym of 'round' here.
        self.current_word = None
        #
        ModalDialog.__init__(self, parent, *a, **kw)
        # navigate to the first word if exists
        self.word_first()

    def body(self, master):
        frm = tk.Frame(self)
        frm.pack(side=tk.TOP, fill=tk.X)
        tk.Label(frm, text='Font').pack(side=tk.LEFT)
        fonts = tkFont.families(self)
        self.font_family.set(ReciteWord.DEFAULT_FONT)
        tk.OptionMenu(frm, self.font_family, *fonts).pack(side=tk.LEFT)
        tk.Spinbox(frm, from_=10, to=36, increment=1, textvariable=self.font_size, width=3).pack(side=tk.LEFT)
        tk.Button(frm, text='Apply', command=self.use_font).pack(side=tk.LEFT)
        tk.Button(frm, text='Modify', command=self.edit_word).pack(side=tk.RIGHT)
        tk.Checkbutton(frm, variable=self.switch_hide, textvariable=self.switch_label, command=self.on_switch_changed).\
            pack(side=tk.RIGHT)
        ttk.Separator(master, orient=tk.HORIZONTAL).pack(side=tk.TOP, fill=tk.X)
        frm = tk.Frame(master)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self.canvas = tk.Canvas(frm, confine=True)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES)
        scroll = tk.Scrollbar(frm, orient=tk.VERTICAL, command=self.canvas.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.config(yscrollcommand=scroll.set)
        scroll = tk.Scrollbar(master, orient=tk.HORIZONTAL, command=self.canvas.xview)
        scroll.pack(side=tk.TOP, fill=tk.X)
        self.canvas.config(xscrollcommand=scroll.set)
        self.canvas.tag_bind('CLICK_AREA', '<Button-1>', self.on_click_mask)  # left mouse button pressed
        self.canvas.tag_bind('CLICK_AREA', '<B1-Motion>', self.on_move_mask)  # left mouse button moved
        self.canvas.bind('<MouseWheel>', self.on_canvas_scroll)         # up or down
        self.canvas.bind('<Shift-MouseWheel>', self.on_canvas_scroll2)  # left or right

    def buttonbox(self):
        box = tk.Frame(self)
        box.pack()
        options = {'side': tk.LEFT, 'padx': 5, 'pady': 5}
        w = tk.Button(box, text="|<-", command=self.word_first)
        w.pack(**options)
        w = tk.Button(box, text="<-", command=self.word_prev)
        w.pack(**options)
        w = tk.Button(box, text="->", command=self.word_next)
        w.pack(**options)
        w = tk.Button(box, text="->|", command=self.word_last)
        w.pack(**options)
        ttk.Separator(box, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.BOTH, padx=5)
        w = tk.Button(box, text=u"\u274c", command=self.fail_current_word)
        w.pack(**options)
        if self.mode == ReciteWord.MODE_TEST:
            w = tk.Button(box, text=u'\u2705', command=self.pass_current_word)
            w.pack(**options)
        w = tk.Button(box, text=u'\u23ce', command=self.reset_current_word)
        w.pack(**options)
        ttk.Separator(box, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.BOTH, padx=5)
        w = tk.Button(box, text="Close", command=self.ok)
        w.pack(**options)
        # ---- hot key ----
        self.bind("<Left>", self.word_prev)
        self.bind("<Right>", self.word_next)
        self.bind("<Down>", self.word_last)
        if self.mode == ReciteWord.MODE_TEST:
            self.bind("<Return>", self.pass_current_word)
        self.bind("<Escape>", self.ok)

    def word_next(self, event=None):
        hide_tested = self.switch_hide.get()
        for n in range(self.current_word+1, len(self.words)):
            if hide_tested and self.words[n].untested is False:
                continue
            else:
                self.draw_word(n)
                self.reset_title()
                break
        else:
            self.draw_empty()

    def word_prev(self, event=None):
        if self.current_word == -1:
            self.current_word = len(self.words)
        hide_tested = self.switch_hide.get()
        for n in range(self.current_word-1, -1, -1):
            if hide_tested and self.words[n].untested is False:
                continue
            else:
                self.draw_word(n)
                self.reset_title()
                break
        else:
            self.draw_empty()

    def word_first(self, event=None):
        hide_tested = self.switch_hide.get()
        for n in range(len(self.words)):
            if hide_tested and self.words[n].untested is False:
                continue
            elif n == self.current_word:
                break
            else:
                self.draw_word(n)
                self.reset_title()
                break
        else:
            self.draw_empty()

    def word_last(self, event=None):
        hide_tested = self.switch_hide.get()
        for n in range(len(self.words)-1, -1, -1):
            if hide_tested and self.words[n].untested is False:
                continue
            elif n == self.current_word:
                break
            else:
                self.draw_word(n)
                self.reset_title()
                break
        else:
            self.draw_empty()

    def load_words(self, turn):
        """
        @param turn if present, retrieve all words due to review; if not, retrieve
        the words learned just today.
        """
        if turn is None:
            words = self._db.retrieve_today()
        else:
            words = self._db.retrieve_due(turn)
        return words

    def draw_word(self, index):
        self.current_word = index
        word = self.words[index]
        self.canvas.delete(tk.ALL)
        x = ReciteWord.FONT_HEIGHT
        y = ReciteWord.FONT_HEIGHT + ReciteWord.LINE_SPACE
        hide_tested = self.switch_hide.get()
        for n, pt in enumerate(word.points):
            tid = self.canvas.create_text(x, y, anchor=tk.NW, text=pt.value, font=self.font)
            box = self.canvas.bbox(tid)
            length = max((box[2]-box[0]), self.font.measure(pt.facet))
            box = (box[0], box[1], box[0]+length, box[3])
            y += box[3] - box[1] + ReciteWord.LINE_SPACE
            if word.untested and hide_tested:
                tags = [str(n), 'CLICK_AREA']
                self.canvas.create_rectangle(*box, outline='black', fill='gray', tags=tags)
                self.canvas.create_text((box[0]+box[2])/2, (box[1]+box[3])/2, text=pt.facet, font=self.font, tags=tags)
        # display score
        if word.untested is False:
            score = u'\u2713' if word.passed else u'\u274c'
            self.canvas.create_text(x, y+ReciteWord.FONT_HEIGHT+ReciteWord.LINE_SPACE,
                                    anchor=tk.NW, text=score, font=self.font)
        # resize
        box = self.canvas.bbox(tk.ALL)
        self.canvas.config(scrollregion=(0, 0, box[2], box[3]))

    def draw_empty(self):
        self.current_word = -1
        self.canvas.delete(tk.ALL)
        text = '<EMPTY>'
        self.canvas.create_text(ReciteWord.FONT_HEIGHT, ReciteWord.FONT_HEIGHT, anchor=tk.NW, text=text, font=self.font)
        self.reset_title()

    def fail_current_word(self):
        if self.current_word < 0:
            return
        self.words[self.current_word].mark_as_fail()
        if self.switch_hide.get():
            self.word_next()

    def pass_current_word(self, event=None):
        if self.current_word < 0:
            return
        self.words[self.current_word].mark_as_pass()
        if self.switch_hide.get():
            self.word_next()

    def reset_current_word(self):
        if self.current_word < 0:
            return
        self.words[self.current_word].mark_as_untested()

    def use_font(self):
        family = self.font_family.get()
        size = int(self.font_size.get())
        try:
            self.font = tkFont.Font(family=family, size=size)
        except tk.TclError as e:
            self.font = tkFont.Font(family=family, size=size, exists=True)
        finally:
            ReciteWord.FONT_HEIGHT = self.font.metrics('linespace')
            ReciteWord.LINE_SPACE = ReciteWord.FONT_HEIGHT / 3
            if self.current_word != -1:
                self.draw_word(self.current_word)
            else:
                self.draw_empty()

    def on_click_mask(self, event):
        canvasx, canvasy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        mask = self.canvas.find_closest(canvasx, canvasy)
        if self.canvas.type(mask[0]) == 'text':
            mask2 = self.canvas.find_below(mask[0])
            still = self.canvas.find_below(mask2[0])
            self.moved_objs = (mask[0], mask2[0])  # text, rect
        else:
            mask2 = self.canvas.find_above(mask[0])
            still = self.canvas.find_below(mask[0])
            self.moved_objs = (mask2[0], mask[0])  # text, rect
        box = self.canvas.bbox(still)
        self.move_param = (event.x, event.y, box[1], box[3])

    def on_move_mask(self, event):
        dx, dy = event.x-self.move_param[0], event.y-self.move_param[1]
        coord = self.canvas.coords(self.moved_objs[1])
        text_h = self.move_param[3] - self.move_param[2]
        if text_h + coord[3] + dy < self.move_param[3]:
            dy = 0
        elif self.move_param[2] + text_h < coord[1] + dy:
            dy = 0
        map(lambda i: self.canvas.move(i, dx, dy), self.moved_objs)
        self.move_param = (event.x, event.y, self.move_param[2], self.move_param[3])

    def on_canvas_scroll(self, event):
        self.canvas.yview_scroll(event.delta/ReciteWord.SCROLL_STEP, tk.UNITS)

    def on_canvas_scroll2(self, event):
        self.canvas.xview_scroll(event.delta/ReciteWord.SCROLL_STEP, tk.UNITS)

    def apply(self):
        """
        Commit all changes to database when closing the dialog.
        """
        changed = [i for i in self.words if not i.untested]
        if len(changed) > 0:
            self._db.update_progress(changed)

    def reset_title(self):
        if self.current_word == -1:
            self.title(self.title_base)
        else:
            self.title('%s %d / %d' % (self.title_base, self.current_word+1, len(self.words)))

    def on_switch_changed(self):
        if self.switch_hide.get() == 0:
            self.switch_label.set(u'\u263a')  # show all
        else:
            self.switch_label.set(u'\u2639')  # only show untested words
        if self.current_word != -1:
            self.draw_word(self.current_word)

    def edit_word(self):
        if self.current_word == -1:
            return
        dlg = EditWord(self, title='[%s] Modify Word Entry' % self._db.table,
                       source=self._db,
                       word=self.words[self.current_word])
        dlg.show()
        if dlg.result is None:
            return
        self.draw_word(self.current_word)


class MainWindow(tk.Tk):
    def __init__(self, *a, **kw):
        tk.Tk.__init__(self, *a, **kw)
        self.title('Word-Pal')
        options = {'side': tk.TOP, 'padx': 5, 'pady': 5, 'fill': tk.BOTH, 'expand': tk.YES}
        self.source_frm = SpecifyWordStoreFrame(self)
        self.source_frm.pack(**options)
        self.btn_text = tk.StringVar(value='Data Source: ?')
        tk.Button(self, textvariable=self.btn_text, command=self.specify_source).pack(**options)
        tk.Button(self, text='Input a New Word', command=self.start_input).pack(**options)
        frm = tk.LabelFrame(self, text='Specify Review Range')
        frm.pack(**options)
        tk.Button(frm, text='Start Recite', command=self.start_review).pack(**options)
        sub = tk.Frame(frm)
        sub.pack(**options)
        tk.Label(sub, text='Review Round:').pack(side=tk.LEFT)
        self.turn = tk.IntVar(value=1)
        spin = tk.Spinbox(sub, textvariable=self.turn, command=self.update_word_count, justify=tk.CENTER)
        spin.config(from_=1, to=100, increment=1)
        spin.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        sub = tk.Frame(frm)
        sub.pack(**options)
        tk.Label(sub, text='Words Total:').pack(side=tk.LEFT)
        self.count = tk.StringVar(value='?')
        tk.Entry(sub, textvariable=self.count, state=tk.DISABLED, justify=tk.CENTER).\
            pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        tk.Button(self, text="Today's Words", command=self.view_today).pack(**options)
        self.word_source = None
        self.enhance_functions()

    def specify_source(self):
        # 1. close old database
        if self.word_source is not None:
            self.word_source.close()
            self.word_source = None
        source = self.source_frm.word_source()
        if source is None:
            return
        # 2. open new database
        self.word_source = WordStore(*source)
        self.update_word_count()
        self.btn_text.set('Data Source: %s' % self.word_source.table)

    def start_review(self):
        if self.word_source is None:
            return
        ReciteWord(self, source=self.word_source, turn=self.turn.get(), title='Word Test').show()
        self.update_word_count()

    def view_today(self):
        """
        Review all words again that have been reviewed/edited today.
        """
        if self.word_source is None:
            return
        ReciteWord(self, source=self.word_source, title="Today's Words").show()

    def start_input(self):
        if self.word_source is None:
            return
        EditWord(self, title='[%s] Input A Word Entry' % self.word_source.table, source=self.word_source).show()

    def update_word_count(self):
        n = self.word_source.review_num(self.turn.get())
        self.count.set(n)

    def enhance_functions(self):
        #
        self.bind_class('Text', '<Mod1-a>', TextOps.select_all)
        self.bind_class('Text', '<Mod1-A>', TextOps.select_all)
        self.bind_class('Text', '<Mod1-Left>', TextOps.jump_to_start)
        self.bind_class('Text', '<Mod1-Right>', TextOps.jump_to_end)
        self.bind_class('Text', '<Mod1-Up>', TextOps.jump_top)
        self.bind_class('Text', '<Mod1-Down>', TextOps.jump_bottom)
        self.bind_class('Text', '<Mod1-C>', TextOps.copy)
        self.bind_class('Text', '<Mod1-X>', TextOps.cut)
        self.bind_class('Text', '<Mod1-V>', TextOps.paste)
        # TODO: why doesn't work?
        '''
        self.bind_class('Entry', '<Mod1-a>', EntryOps.select_all)
        self.bind_class('Entry', '<Mod1-A>', EntryOps.select_all)
        self.bind_class('Entry', '<Mod1-Left>', EntryOps.jump_to_start)
        self.bind_class('Combobox', '<Mod1-Right>', EntryOps.jump_to_end)
        self.bind_class('Combobox', '<Mod1-C>', EntryOps.copy)
        self.bind_class('Combobox', '<Mod1-X>', EntryOps.cut)
        self.bind_class('Combobox', '<Mod1-V>', EntryOps.paste)
        '''


if __name__ == '__main__':
    MainWindow().mainloop()