#!usr/bin/env python
# -*- coding:utf-8 -*-

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox


class WebPageHandler:
    def __init__(self):
        self._links = []

    def analyze(self, url):
        self._links[:] = None
        return self._links


class MainWnd(tk.Frame):
    WND_TITLE = 'Manga Crawler'

    def __init__(self, master, *a, **kw):
        tk.Frame.__init__(self, master, *a, **kw)
        #
        frame = tk.Frame(self)
        frame.pack(side=tk.TOP, expand=tk.NO, fill=tk.BOTH)
        lbl = tk.Label(frame, text='URL:')
        lbl.pack(side=tk.LEFT)
        lbl.bind('<Double-Button-1>', self.onclick_clear_url)
        self._url = tk.StringVar()
        tk.Entry(frame, textvariable=self._url).pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
        btn = tk.Button(frame, text='Analyze', command=self.onclick_analyze_url)  # download m3u8 file (index file)
        btn.pack(side=tk.LEFT)
        #
        frame = tk.Frame(self)
        frame.pack(side=tk.TOP, expand=tk.NO, fill=tk.BOTH)
        tk.Label(frame, text='Dir:').pack(side=tk.LEFT)
        self._dir = tk.StringVar()
        tk.Entry(frame, textvariable=self._dir).pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
        tk.Button(frame, text='Save to', command=self.onclick_browse_dir).pack(side=tk.LEFT)
        #
        group = tk.LabelFrame(self, text='Links')
        group.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        # row 1 -- step 2
        frame = tk.Frame(group, padx=5, pady=5)
        frame.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        self._segments = ttk.Treeview(frame, selectmode=tk.EXTENDED, show='headings', columns=('sn', 'url', 'state'))
        self._segments.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        yscroll = tk.Scrollbar(frame, orient=tk.VERTICAL, command=self._segments.yview)
        yscroll.pack(side=tk.RIGHT, expand=tk.NO, fill=tk.Y)
        self._segments['yscrollcommand'] = yscroll.set
        xscroll = tk.Scrollbar(group, orient=tk.HORIZONTAL, command=self._segments.xview)
        xscroll.pack(side=tk.TOP, expand=tk.NO, fill=tk.X)
        self._segments['xscrollcommand'] = xscroll.set
        self._segments.bind('<Key-K>', self.onkey_tree_delete)
        self._segments.bind('<1>', self.onkey_tree_click)
        self._segments.heading('sn', text='SN')
        self._segments.heading('url', text='URL')  # '#0' column is icon and it's hidden here
        self._segments.heading('state', text='State')    # we only need two columns: '#1' and '#2'
        self._segments.column('sn', width=30, stretch=False)
        self._segments.column('state', width=50, stretch=False, anchor=tk.CENTER)
        #
        frame = tk.Frame(self)
        frame.pack(side=tk.TOP, expand=tk.NO, fill=tk.BOTH)
        tk.Label(frame, text='Threads:').pack(side=tk.LEFT)
        self._job_num = tk.IntVar()
        tk.Spinbox(frame, textvariable=self._job_num, from_=1, to=10, width=2).pack(side=tk.LEFT)
        tk.Label(frame, text='Timeout:').pack(side=tk.LEFT)
        self._timeout = tk.IntVar()
        tk.Spinbox(frame, textvariable=self._timeout, from_=3, to=9, width=2).pack(side=tk.LEFT)
        self._btn = tk.Button(frame, text='Download', command=self.onclick_download_segments)
        self._btn.pack(side=tk.LEFT)

        self._handler = WebPageHandler()

    def onclick_clear_url(self):
        pass

    def onclick_analyze_url(self):
        url = self._url.get().strip()
        if len(url) == 0:
            return
        links = self._handler.analyze(url)

    def onclick_browse_dir(self):
        a_dir = filedialog.askdirectory()
        if a_dir == '':
            return
        self._dir.set(a_dir)

    def onkey_tree_delete(self):
        pass

    def onkey_tree_click(self, _):
        pass

    def onclick_download_segments(self):
        pass


def main():
    try:
        root = tk.Tk()
        root.title(MainWnd.WND_TITLE)
        MainWnd(root).pack(fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        root.mainloop()
    except Exception as e:
        print(e)

if __name__ == '__main__':
    main()
