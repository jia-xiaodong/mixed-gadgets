#!usr/bin/env python
# -*- coding:utf-8 -*-

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
import threading
import queue
from urllib.request import urlopen
from urllib.request import Request
from hashlib import md5
import os
from enum import Enum
from html.parser import HTMLParser

import ssl
ssl._create_default_https_context = ssl._create_unverified_context


def url_split(url):
    sep = url.rfind('/')
    name = url[sep+1:]
    dot = name.rfind('.')
    return url[:sep], name[:dot], name[dot+1:]


class WebPageHandler(HTMLParser):
    def __init__(self, *a, **kw):
        HTMLParser.__init__(self, *a, **kw)
        self._images = []
        self._chapter_pages_found = False
        self._chapter_page_found = False
        self._image_found = False

    def feed_file(self, web_page_file):
        self._images[:] = []
        with open(web_page_file, 'r') as file:
            self.feed(file.read())
        self.close()
        return self._images

    def handle_starttag(self, tag, attrs):
        if not self._chapter_pages_found:
            if tag == 'div' and self.attr_has(attrs, ('class', 'chapter-pages')):
                self._chapter_pages_found = True
        elif not self._chapter_page_found:
            if tag == 'div' and self.attr_has(attrs, ('class', 'chapter-page')):
                self._chapter_page_found = True
        elif tag == 'img' and self.attr_name(attrs, 'src'):
            self._images.append(self.attr_value(attrs, 'src'))

    def handle_endtag(self, tag):
        if self._chapter_pages_found and self._chapter_page_found:
            if tag == 'div':
                self._chapter_page_found = False

    @staticmethod
    def attr_has(attrs, attr):
        for i in attrs:
            if i == attr:
                return True
        return False

    @staticmethod
    def attr_name(attrs, name):
        for i in attrs:
            if i[0] == name:
                return True
        return False

    @staticmethod
    def attr_value(attrs, name):
        for i in attrs:
            if i[0] == name:
                return i[1]
        return None


class DownloadStatus(Enum):
    Unknown = 0
    Successful = 1
    Failed = 2


class ThreadDownloader(threading.Thread):
    def __init__(self, url, dst, timeout=3, callback=None):
        threading.Thread.__init__(self)
        self._url = url  # source URL
        self._dst = dst  # destination folder
        self._timeout = timeout
        self._cb = callback
        self._status = DownloadStatus.Unknown

    def run(self):
        try:
            user_agent = {'User-Agent': 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_8; en-us) AppleWebKit/534.50'}
            req = Request(self._url, headers=user_agent, unverifiable=True)
            ifo = urlopen(req, timeout=self._timeout)
            content = ifo.read()
            ifo.close()
            self._size = len(content)
            if not self.file_exists(content):
                with open(self._dst, 'wb') as ofo:
                    ofo.write(content)
            self._status = DownloadStatus.Successful
            if self._cb is not None:
                self._cb(self)
        except Exception as e:
            print('%s: %s' % (self._url, e))
            self._status = DownloadStatus.Failed
            if self._cb is not None:
                self._cb(self)

    def file_exists(self, content):
        """
        check if file exists already on local disk.
        @param filename: local disk filename (full dir + base name)
        @param content: is belonging to remote resource.
        @return: True if it exists
        """
        if not os.path.exists(self._dst):
            return False
        if not os.path.isfile(self._dst):
            return False
        if os.path.getsize(self._dst) != len(content):
            return False
        with open(self._dst, 'rb') as ofo:
            old = ofo.read()
            digest1 = md5(old).digest()
            digest2 = md5(content).digest()
            return digest1 == digest2

    def is_successful(self):
        return self._status == DownloadStatus.Successful

    def file_path(self):
        return self._dst


class MainWnd(tk.Frame):
    WND_TITLE = 'Manga Crawler'
    WEB_PAGE = 'index.html'

    def __init__(self, master, *a, **kw):
        tk.Frame.__init__(self, master, *a, **kw)
        #
        frame = tk.Frame(self)
        frame.pack(side=tk.TOP, expand=tk.NO, fill=tk.BOTH)
        lbl = tk.Label(frame, text='URL:')
        lbl.pack(side=tk.LEFT)
        lbl.bind('<Double-Button-1>', lambda _: self._url.set(''))
        self._url = tk.StringVar()
        tk.Entry(frame, textvariable=self._url).pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
        btn = tk.Button(frame, text='Download', command=self.onclick_analyze_url)  # download m3u8 file (index file)
        btn.pack(side=tk.LEFT)
        tk.Button(frame, text='Paste from CB', command=self.paste_from_clipboard).pack(side=tk.LEFT)
        #
        frame = tk.Frame(self)
        frame.pack(side=tk.TOP, expand=tk.NO, fill=tk.BOTH)
        tk.Label(frame, text='Dir:').pack(side=tk.LEFT)
        self._tmp_dir = tk.StringVar()
        tk.Entry(frame, textvariable=self._tmp_dir).pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
        tk.Button(frame, text='Save to Dir', command=self.onclick_browse_dir).pack(side=tk.LEFT)
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
        frame = tk.Frame(group)
        frame.pack(side=tk.TOP, expand=tk.NO, fill=tk.BOTH)
        tk.Label(frame, text='Progress: ').pack(side=tk.LEFT)
        self._progress = tk.IntVar()
        self._progressbar = ttk.Progressbar(frame, mode='determinate', variable=self._progress)
        self._progressbar.pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
        #
        frame = tk.Frame(self)
        frame.pack(side=tk.TOP, expand=tk.NO, fill=tk.BOTH)
        tk.Button(frame, text='Read Local Web Page', command=self.load_local_web_page).pack(side=tk.LEFT)
        tk.Label(frame, text='Threads:').pack(side=tk.LEFT)
        self._job_num = tk.IntVar()
        tk.Spinbox(frame, textvariable=self._job_num, from_=1, to=10, width=2).pack(side=tk.LEFT)
        tk.Label(frame, text='Timeout:').pack(side=tk.LEFT)
        self._timeout = tk.IntVar()
        tk.Spinbox(frame, textvariable=self._timeout, from_=3, to=9, width=2).pack(side=tk.LEFT)
        self._btn = tk.Button(frame, text='Download Images', command=self.onclick_download_segments)
        self._btn.pack(side=tk.LEFT)

        self._handler = WebPageHandler()
        self._job_queue = queue.Queue()
        self._downloaders = []
        self._running = False

    def onclick_analyze_url(self):
        url = self._url.get().strip()
        dst = self._tmp_dir.get().strip()
        if len(url) == 0 or len(dst) == 0:
            return
        if not os.path.exists(dst):
            os.mkdir(dst)
        job = ThreadDownloader(url, os.path.join(dst, MainWnd.WEB_PAGE), self._timeout.get(), self.on_web_page_downloaded)
        job.start()

    def on_web_page_downloaded(self, job: ThreadDownloader):
        if not job.is_successful():
            messagebox.showerror(MainWnd.WND_TITLE, 'Failed to download web page')
            return
        # populate UI with image URLs
        links = self._handler.feed_file(job.file_path())
        self._segments.delete(*self._segments.get_children())
        for i, url in enumerate(links, start=1):
            iid = 'I%04d' % i
            self._segments.insert('', tk.END, iid=iid, values=(i, url, ''))

    def load_local_web_page(self):
        dst = self._tmp_dir.get().strip()
        if len(dst) == 0:
            return
        web_page = os.path.join(dst, MainWnd.WEB_PAGE)
        if not os.path.exists(web_page):
            return
        links = self._handler.feed_file(web_page)
        self._segments.delete(*self._segments.get_children())
        for i, url in enumerate(links, start=1):
            iid = 'I%04d' % i
            self._segments.insert('', tk.END, iid=iid, values=(i, url, ''))

    def paste_from_clipboard(self):
        url = self.clipboard_get().strip()
        if len(url) > 0:
            self._url.set(url)

    def onclick_browse_dir(self):
        a_dir = filedialog.askdirectory()
        if a_dir == '':
            return
        self._tmp_dir.set(a_dir)

    def onkey_tree_delete(self):
        pass

    def onkey_tree_click(self, _):
        pass

    def onclick_download_segments(self):
        urls = self._segments.get_children()
        if len(urls) == 0:
            return
        #
        if self._running:
            self._running = False   # global signal to stop running jobs
            self._btn.config(text='Download')
            for i in self._downloaders:
                i.join()
            self._downloaders[:] = []
            return
        #
        self._running = True
        self._btn.config(text='Cancel')
        try:
            self.clear_queue()
            for i in urls:
                self._job_queue.put(i)
                self._segments.set(i, column='state', value='')
            #
            self._progress.set(0)
            self._progressbar.config(maximum=self._job_queue.qsize())
            #
            self.after(100, self.update_progress)
        except Exception as e:
            print(e)
            self._btn.config(text='Download')
            self._running = False

    def clear_queue(self):
        self._downloaders[:] = []
        while not self._job_queue.empty():
            self._job_queue.get()

    def update_progress(self):
        """
        update UI
        """
        finished = 0
        for i in self._downloaders[:]:
            if i.isAlive():
                continue
            # visualize task state: completion or failure
            if i.is_successful():
                self._segments.delete(i.iid)
            else:
                self._segments.set(i.iid, column='state', value='X')
            self._downloaders.remove(i)
            finished += 1
        if finished > 0:
            self._progress.set(self._progress.get() + finished)
        #
        free_slots = max(self._job_num.get() - len(self._downloaders), 0)
        to_be_added = min(free_slots, self._job_queue.qsize())
        for i in range(0, to_be_added):
            iid = self._job_queue.get()
            #  [ Important Point about ttk.Treeview ]
            # no matter what type it was when inserted into 'values',
            # it is str of type now when being retrieved.
            #
            # In short, be careful of below 'sn' in this app.
            sn, url, state = self._segments.item(iid, 'values')
            _, _, ext = url_split(url)
            dst = os.path.join(self._tmp_dir.get(), 'img_%04d.%s' % (int(sn), ext))
            job = ThreadDownloader(url, dst, self._timeout.get())
            job.iid = iid  # attach a temporary attribute
            self._downloaders.append(job)
            job.start()
            self._segments.set(iid, column='state', value='...')
        #
        if len(self._downloaders) > 0:
            self.after(100, self.update_progress)
        else:
            self._running = False
            self._btn.config(text='Download')
            messagebox.showinfo(MainWnd.WND_TITLE, 'All segments are downloaded.')


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
