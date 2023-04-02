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
from urllib.parse import quote, quote_plus, urlparse
from hashlib import md5
import os
from enum import Enum
from html.parser import HTMLParser
import re

import ssl
ssl._create_default_https_context = ssl._create_unverified_context


def url_image_name(url):
    match = re.search(r'/(?P<base>\w+)\.(?P<ext>(jpg|png))', url)
    if match:
        return match.group('base'), match.group('ext')
    return None, None


def url_quote(url):
    parts = urlparse(url)
    quoted = [parts.scheme, quote(parts.netloc), quote(parts.path), quote(parts.params),
              quote_plus(parts.query, safe='='), quote_plus(parts.fragment)]
    result = '{}://{}{}'.format(quoted[0], quoted[1], quoted[2])
    if len(quoted) > 3 and len(quoted[3]) > 0:
        result = '{};{}'.format(result, quoted[3])  # params
    if len(quoted) > 4 and len(quoted[4]) > 0:
        result = '{}?{}'.format(result, quoted[4])  # query
    if len(quoted) > 5 and len(quoted[5]) > 0:
        result = '{}#{}'.format(result, quoted[5])  # fragment
    return result


class WebPageHandler(HTMLParser):
    domain_name = None
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._images = []

    def feed_file(self, web_page_file):
        self._images[:] = []
        with open(web_page_file, 'r') as file:
            self.feed(file.read())
        self.close()
        return self._images

    @staticmethod
    def attrs_has_attr(attrs, attr):
        for i in attrs:
            if i == attr:
                return True
        return False

    @staticmethod
    def attrs_has_name(attrs, name):
        for i in attrs:
            if i[0] == name:
                return True
        return False

    @staticmethod
    def attrs_get_value(attrs, name):
        for i in attrs:
            if i[0] == name:
                return i[1]
        return None


class HachiRawHandler(WebPageHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._chapter_pages_found = False
        self._chapter_page_found = False
        self._image_found = False
        self.domain_name = 'hachiraw.com'

    def handle_starttag(self, tag, attrs):
        if not self._chapter_pages_found:
            if tag == 'div' and self.attrs_has_attr(attrs, ('class', 'chapter-pages')):
                self._chapter_pages_found = True
        elif not self._chapter_page_found:
            if tag == 'div' and self.attrs_has_attr(attrs, ('class', 'chapter-page')):
                self._chapter_page_found = True
        elif tag == 'img' and self.attrs_has_name(attrs, 'src'):
            url = self.attrs_get_value(attrs, 'src')
            self._images.append(url.strip())

    def handle_endtag(self, tag):
        if self._chapter_pages_found and self._chapter_page_found:
            if tag == 'div':
                self._chapter_page_found = False


class ParallelParadiseOnlineHandler(WebPageHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.domain_name = 'www.parallelparadise.online'
        self._reading_content_found = False
        self._page_break_found = False

    def handle_starttag(self, tag, attrs):
        if not self._reading_content_found:
            if tag == 'div' and self.attrs_has_attr(attrs, ('class', 'reading-content')):
                self._reading_content_found = True
        elif not self._page_break_found:
            if tag == 'div' and self.attrs_has_attr(attrs, ('class', 'page-break ')):
                self._page_break_found = True
        elif tag == 'img' and self.attrs_has_attr(attrs, ('class', 'wp-manga-chapter-img')):
            url = self.attrs_get_value(attrs, 'src')
            self._images.append(url.strip())

    def handle_endtag(self, tag):
        if self._reading_content_found and self._page_break_found:
            if tag == 'div':
                self._page_break_found = False


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
        frame = tk.Frame(self)
        frame.pack(side=tk.TOP, expand=tk.NO, fill=tk.BOTH)
        tk.Label(frame, text='Hanlder:').pack(side=tk.LEFT)
        self._handlers = dict()
        for handler in [HachiRawHandler(), ParallelParadiseOnlineHandler()]:
            self._handlers[handler.domain_name] = handler
        self._active_handler = tk.StringVar()
        tk.OptionMenu(frame, self._active_handler, *self._handlers.keys()).pack(side=tk.LEFT)
        #
        group = tk.LabelFrame(self, text='Links')
        group.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        # row 1 -- step 2
        frame = tk.Frame(group, padx=5, pady=5)
        frame.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        self._links = ttk.Treeview(frame, selectmode=tk.EXTENDED, show='headings', columns=('sn', 'url', 'state'))
        self._links.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        yscroll = tk.Scrollbar(frame, orient=tk.VERTICAL, command=self._links.yview)
        yscroll.pack(side=tk.RIGHT, expand=tk.NO, fill=tk.Y)
        self._links['yscrollcommand'] = yscroll.set
        xscroll = tk.Scrollbar(group, orient=tk.HORIZONTAL, command=self._links.xview)
        xscroll.pack(side=tk.TOP, expand=tk.NO, fill=tk.X)
        self._links['xscrollcommand'] = xscroll.set
        self._links.bind('<Key-K>', self.onkey_tree_delete)
        self._links.bind('<1>', self.onkey_tree_click)
        self._links.heading('sn', text='SN')
        self._links.heading('url', text='URL')  # '#0' column is icon and it's hidden here
        self._links.heading('state', text='State')    # we only need two columns: '#1' and '#2'
        self._links.column('sn', width=30, stretch=False)
        self._links.column('state', width=50, stretch=False, anchor=tk.CENTER)
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
        #
        self._auto = tk.BooleanVar(value=True)
        tk.Checkbutton(frame, text='Auto', variable=self._auto).pack(side=tk.RIGHT)

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
        url = url_quote(url)
        job = ThreadDownloader(url, os.path.join(dst, MainWnd.WEB_PAGE), self._timeout.get(), self.on_web_page_downloaded)
        job.start()

    def on_web_page_downloaded(self, job: ThreadDownloader):
        if not job.is_successful():
            messagebox.showerror(MainWnd.WND_TITLE, 'Failed to download web page')
            return
        parse_result = urlparse(job._url)
        if parse_result.netloc not in self._handlers:
            return
        self._active_handler.set(parse_result.netloc)
        self.load_links(job.file_path(), parse_result.netloc)

    def load_local_web_page(self):
        dst = self._tmp_dir.get().strip()
        if len(dst) == 0:
            return
        web_page = self.web_page()
        if not os.path.exists(web_page):
            return
        active_handler = self._active_handler.get()
        if len(active_handler) == 0:
            return
        self.load_links(web_page, active_handler)

    def load_links(self, file, active_handler):
        links = self._handlers[active_handler].feed_file(file)
        self._links.delete(*self._links.get_children())
        for i, url in enumerate(links, start=1):
            iid = 'I%04d' % i
            self._links.insert('', tk.END, iid=iid, values=(i, url, ''))
        if self._auto.get():
            self.onclick_download_segments()

    def paste_from_clipboard(self):
        url = self.clipboard_get().strip()
        if len(url) > 0:
            self._url.set(url)

    def onclick_browse_dir(self):
        a_dir = filedialog.askdirectory()
        if a_dir == '':
            return
        self._tmp_dir.set(a_dir)

    def onkey_tree_delete(self, _):
        # keep treeview items intact when downloading, because jobs are in queue.
        if self._running:
            return
        #
        selected = self._links.selection()
        num = len(selected)
        if num == 0:
            return
        if num == 1:
            msg = 'Are you sure to delete\n\n%s\n\n?' % selected[0]
        else:
            msg = 'Are you sure to delete %d jobs?' % num
        if not messagebox.askokcancel(MainWnd.WND_TITLE, msg):
            return
        self._links.delete(*selected)

    def onkey_tree_click(self, _):
        selected = self._links.selection()
        if len(selected) == 0:
            return
        _, url, _ = self._links.item(selected[0], 'values')
        self.clipboard_clear()
        self.clipboard_append(url)

    def onclick_download_segments(self):
        urls = self._links.get_children()
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
                self._links.set(i, column='state', value='')
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
        if not self._running:
            return

        finished = 0
        for i in self._downloaders[:]:
            if i.isAlive():
                continue
            # visualize task state: completion or failure
            if i.is_successful():
                self._links.delete(i.iid)
            else:
                self._links.set(i.iid, column='state', value='X')
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
            sn, url, state = self._links.item(iid, 'values')
            _, ext = url_image_name(url)
            url = url_quote(url)
            dst = os.path.join(self._tmp_dir.get(), 'img_%04d.%s' % (int(sn), ext))
            job = ThreadDownloader(url, dst, self._timeout.get())
            job.iid = iid  # attach a temporary attribute
            self._downloaders.append(job)
            job.start()
            self._links.set(iid, column='state', value='...')
        #
        if len(self._downloaders) > 0:
            self.after(100, self.update_progress)
        else:
            self.after(100, self.notify_finish)

    def notify_finish(self):
        self._running = False
        self._btn.config(text='Download')
        if len(self._links.get_children()) == 0:
            os.remove(self.web_page())
        messagebox.showinfo(MainWnd.WND_TITLE, 'All segments are downloaded.')

    def web_page(self):
        dst = self._tmp_dir.get().strip()
        return os.path.join(dst, MainWnd.WEB_PAGE)

    def on_choose_handler(self, _):
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
