#!usr/bin/env python
# -*- coding:utf-8 -*-

import Tkinter as tk
import tkFileDialog
import tkMessageBox
import ttk
import os
import urllib
import Queue
import threading
from hashlib import md5


def url_join(base, tail):
    if tail.startswith('/'):
        return '%s%s' % (base, tail)
    else:
        return '%s/%s' % (base, tail)


def url_domain(url):
    start = url.find('//')
    start = url.find('/', start+2)
    return url[:start]


class Downloader(threading.Thread):
    def __init__(self, url, dst):
        threading.Thread.__init__(self)
        self._url = url  # source URL
        self._dst = dst  # destination folder
        self._downloaded = True

    def run(self):
        try:
            ifo = urllib.urlopen(self._url)
            content = ifo.read()
            ifo.close()

            dst = os.path.join(self._dst, os.path.basename(self._url))
            if Downloader.file_exists(dst, content):
                return
            with open(dst, 'wb') as ofo:
                ofo.write(content)
        except Exception as e:
            print('%s: %s' % (self._url, e))
            self._downloaded = False

    def is_downloaded(self):
        if self.isAlive():
            return False
        return self._downloaded

    @staticmethod
    def file_exists(filename, content):
        """
        check if file exists already on local disk.
        @param filename: local disk filename (full dir + base name)
        @param content: is belonging to remote resource.
        @return: True if it exists
        """
        if not os.path.exists(filename):
            return False
        if not os.path.isfile(filename):
            return False
        if os.path.getsize(filename) != len(content):
            return False
        with open(filename, 'rb') as ofo:
            old = ofo.read()
            digest1 = md5(old).digest()
            digest2 = md5(content).digest()
            return digest1 == digest2


class Main(tk.Frame):
    INDEX_FILE = 'm3u8.txt'

    def __init__(self, master, *a, **kw):
        tk.Frame.__init__(self, master, *a, **kw)
        #
        self._msg_queue = Queue.Queue()
        self._job_queue = Queue.Queue()
        self._running = False
        # step 1
        group = tk.LabelFrame(self, text='Step 1: M3U8')
        group.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        # row 1 -- step 1
        frame = tk.Frame(group)
        frame.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        tk.Label(frame, text='URL: ').pack(side=tk.LEFT)
        self._url = tk.StringVar()
        tk.Entry(frame, textvariable=self._url).pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
        btn = tk.Button(frame, text='Download', command=self.download_index_file)  # download m3u8 file (index file)
        btn.pack(side=tk.LEFT)
        # row 2 -- step 1
        frame = tk.Frame(group)
        frame.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        tk.Label(frame, text='Local Dir: ').pack(side=tk.LEFT)
        self._tmp_dir = tk.StringVar()
        tk.Entry(frame, textvariable=self._tmp_dir).pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
        tk.Button(frame, text='browse', command=self.browse_tmp).pack(side=tk.LEFT)
        # step 2
        group = tk.LabelFrame(self, text='Step 2: Segments')
        group.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        # row 1 -- step 2
        frame = tk.Frame(group, padx=5, pady=5)
        frame.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        self._segments = tk.Listbox(frame, height=8)
        self._segments.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        yscroll = tk.Scrollbar(frame, orient=tk.VERTICAL, command=self._segments.yview)
        yscroll.pack(side=tk.RIGHT, expand=tk.NO, fill=tk.Y)
        self._segments['yscrollcommand'] = yscroll.set
        xscroll = tk.Scrollbar(group, orient=tk.HORIZONTAL, command=self._segments.xview)
        xscroll.pack(side=tk.TOP, expand=tk.YES, fill=tk.X)
        self._segments['xscrollcommand'] = xscroll.set
        # row 2 -- step 2
        frame = tk.Frame(group)
        frame.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        tk.Button(frame, text='Read Local M3U8 File', command=self.load_index_file).pack(side=tk.LEFT)
        tk.Label(frame, text='Threads: ').pack(side=tk.LEFT)
        self._job_num = tk.IntVar()
        tk.Spinbox(frame, textvariable=self._job_num, from_=1, to=10, width=2).pack(side=tk.LEFT)
        self._btn = tk.Button(frame, text='Download', command=self.download_segments)
        self._btn.pack(side=tk.LEFT)
        # row 3 -- step 2
        self._progress = tk.IntVar()
        self._progressbar = ttk.Progressbar(group, mode='determinate', variable=self._progress)
        self._progressbar.pack(side=tk.TOP, expand=tk.YES, fill=tk.X)
        # step 3
        group = tk.LabelFrame(self, text='Step 3: Merge')
        group.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        frame = tk.Frame(group)
        frame.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        tk.Label(frame, text='Output: ').pack(side=tk.LEFT)
        self._output = tk.StringVar()
        tk.Entry(frame, textvariable=self._output).pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
        tk.Button(frame, text='Browse', command=self.save_as).pack(side=tk.LEFT)
        tk.Button(frame, text='Merge', command=self.merge_cache).pack(side=tk.LEFT)

    def browse_tmp(self):
        adir = tkFileDialog.askdirectory()
        if adir == '':
            return
        self._tmp_dir.set(adir)

    def save_as(self):
        filename = tkFileDialog.asksaveasfilename(defaultextension='.mp4')
        if filename == '':
            return
        self._output.set(filename)

    def download_index_file(self):
        index_url = self._url.get()
        index_url = index_url.strip()
        if len(index_url) == 0:
            return
        cache_dir = self._tmp_dir.get()
        cache_dir = cache_dir.strip()
        if len(cache_dir) == 0:
            return
        try:
            ifo = urllib.urlopen(index_url)
            content = ifo.read()
            ifo.close()
            dst = os.path.join(cache_dir, Main.INDEX_FILE)
            ofo = open(dst, 'w')
            ofo.write(content)
            ofo.close()
            # UI auto-completion
            url_base = url_domain(index_url)
            list = []
            for line in content.split('\n'):
                if line.startswith('#'):
                    continue
                line = line.strip()
                if len(line) == 0:
                    continue
                line = url_join(url_base, line)
                list.append(line)
            self._segments.delete(0, tk.END)
            self._segments.insert(tk.END, *list)
        except Exception as e:
            print(e)

    def load_index_file(self):
        index_url = self._url.get()
        index_url = index_url.strip()
        if len(index_url) == 0:
            return
        cache_dir = self._tmp_dir.get()
        cache_dir = cache_dir.strip()
        if len(cache_dir) == 0:
            return
        url_base = url_domain(index_url)
        index_file = os.path.join(cache_dir, Main.INDEX_FILE)
        ifo = open(index_file, 'r')
        list = []
        for line in ifo.readlines():
            if line.startswith('#'):
                continue
            line = line.strip()
            if len(line) == 0:
                continue
            line = url_join(url_base, line)
            list.append(line)
        self._segments.delete(0, tk.END)
        self._segments.insert(tk.END, *list)

    def download_segments(self):
        if self._segments.size() == 0:
            return
        #
        if self._running:
            self._running = False
            self._btn.config(text='Download')
            return
        self._running = True
        self._btn.config(text='Cancel')
        try:
            self.clear_queue()
            content = self._segments.get(0, tk.END)
            #content = list(content)
            for i in content:
                self._job_queue.put(i)
            #
            self._progress.set(0)
            self._progressbar.config(maximum=self._job_queue.qsize())
            #
            threading.Thread(target=self.worker_thread).start()
            self.after(100, self.listen_for_progress)
        except Exception as e:
            print(e)
            self._btn.config(text='Download')
            self._running = False

    def clear_queue(self):
        while not self._msg_queue.empty():
            self._msg_queue.get()
        while not self._job_queue.empty():
            self._job_queue.get()

    def worker_thread(self):
        """
        this thread is in charge of spawning enough downloader threads.
        """
        cache = self._tmp_dir.get()
        num = self._job_queue.qsize()
        #
        progress = 0
        jobs = []
        while self._running and progress < num:
            for i in jobs[:]:
                if i.isAlive():
                    continue
                if i.is_downloaded():
                    # remove it from Listbox
                    content = self._segments.get(0, tk.END)
                    index = content.index(i._url)
                    self._segments.delete(index)
                jobs.remove(i)
                # report progress
                progress += 1
                self._msg_queue.put(progress)
            # if user changes settings of concurrent jobs
            slots = max(self._job_num.get() - len(jobs), 0)
            added = min(slots, self._job_queue.qsize())
            for i in range(0, added):
                ts = self._job_queue.get()
                job = Downloader(ts, cache)
                jobs.append(job)
                job.start()
        self._running = False

    def listen_for_progress(self):
        try:
            progress = self._msg_queue.get(False)  # non-block
            self._progress.set(progress)
        except Queue.Empty: # must exist to avoid trace-back
            pass
        finally:
            if self._running:
                self.after(100, self.listen_for_progress)
            else:
                self._btn.config(text='Download')
                tkMessageBox.showinfo('m3u8 downloader', 'All segments are downloaded.')

    def merge_cache(self):
        tmp = self._tmp_dir.get()
        if tmp == '':
            return
        out = self._output.get()
        if out == '':
            return
        #
        videos = [i for i in os.listdir(tmp) if i.endswith('.ts')]
        videos.sort()
        ofo = open(out, 'wb')
        os.chdir(tmp)
        for i in videos:
            ifo = open(i, 'rb')
            ofo.write(ifo.read())
            ifo.close()
        ofo.close()
        tkMessageBox.showinfo('m3u8 downloader', 'Merge is done.')


if __name__ == '__main__':
    root = tk.Tk(className='ts merger')
    Main(root).pack(fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
    root.mainloop()
