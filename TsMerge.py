#!usr/bin/env python
# -*- coding:utf-8 -*-

import Tkinter as tk
import tkFileDialog
import tkMessageBox
import ttk
import os
import urllib2
import Queue
import threading
from hashlib import md5
import time


def url_join(base, tail):
    if tail.startswith('/'):
        return '%s%s' % (base, tail)
    else:
        return '%s/%s' % (base, tail)


def url_domain(url):
    start = url.find('//')
    start = url.find('/', start+2)
    return url[:start]


def url_directory(url):
    start = url.rfind('/')
    return url[:start]


class RepeatTimer:
    """
    Mimic the behavior (interface) of threading.Timer.
    """
    def __init__(self, interval, function):
        self.interval = interval
        self.function = function
        self.thread = threading.Timer(self.interval, self.handle_function)

    def handle_function(self):
        self.function()
        self.thread = threading.Timer(self.interval, self.handle_function)
        self.thread.start()

    def start(self):
        self.thread.start()

    def cancel(self):
        self.thread.cancel()


class DownloadStats(object):
    def __init__(self, refresh_interval):
        self._speed = 0
        self._refresh_interval = refresh_interval

    def init_for_new_download(self, value):
        self._downloaded_size = 0    # bytes
        self._downloaded_blocks = 0  # number of .ts files
        self._total_blocks = value
        self._time_consumed = 0      # seconds
        self.reset(time.time())

    def reset(self, now):
        """
        Speed is measured (updated) in a fixed interval.
        So reset below variables for next interval.
        """
        self._delta_size = 0
        self._start_time = now  # time.time(), float

    def update(self, size):
        """
        Update when every blocks is downloaded.
        """
        self._downloaded_size += size
        self._downloaded_blocks += 1
        self._delta_size += size
        now = time.time()
        dt = now - self._start_time  # dt is float
        self._time_consumed += dt
        if dt >= self._refresh_interval:
            self._speed = self._delta_size / dt
            self.reset(now)

    @property
    def downloaded_size(self):
        return self._downloaded_size

    @property
    def speed(self):
        return self._speed

    @property
    def remaining_time(self):
        if self._downloaded_blocks == 0:
            return 0
        seconds_per_block = self._time_consumed / self._downloaded_blocks
        return seconds_per_block * (self._total_blocks - self._downloaded_blocks)


class Downloader(threading.Thread):
    def __init__(self, url, dst):
        threading.Thread.__init__(self)
        self._url = url  # source URL
        self._dst = dst  # destination folder
        self._size = 0

    def run(self):
        try:
            ifo = urllib2.urlopen(self._url, timeout=3)
            content = ifo.read()
            ifo.close()
            self._size = len(content)

            dst = os.path.join(self._dst, os.path.basename(self._url))
            if Downloader.file_exists(dst, content):
                return
            with open(dst, 'wb') as ofo:
                ofo.write(content)
        except Exception as e:
            print('%s: %s' % (self._url, e))

    def downloaded_size(self):
        return self._size

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
    WND_TITLE = 'TS Merger'
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
        lbl = tk.Label(frame, text='URL: ')
        lbl.pack(side=tk.LEFT)
        lbl.bind('<Double-Button-1>', self.clear_url)
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
        self._segments = tk.Listbox(frame, height=8, selectmode=tk.EXTENDED)
        self._segments.pack(side=tk.LEFT, expand=tk.YES, fill=tk.BOTH)
        yscroll = tk.Scrollbar(frame, orient=tk.VERTICAL, command=self._segments.yview)
        yscroll.pack(side=tk.RIGHT, expand=tk.NO, fill=tk.Y)
        self._segments['yscrollcommand'] = yscroll.set
        xscroll = tk.Scrollbar(group, orient=tk.HORIZONTAL, command=self._segments.xview)
        xscroll.pack(side=tk.TOP, expand=tk.YES, fill=tk.X)
        self._segments['xscrollcommand'] = xscroll.set
        self._segments.bind('<Key-Delete>', self.delete_segments)
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
        frame = tk.Frame(group)
        frame.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        tk.Label(frame, text='Progress: ').pack(side=tk.LEFT)
        self._progress = tk.IntVar()
        self._progressbar = ttk.Progressbar(frame, mode='determinate', variable=self._progress)
        self._progressbar.pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
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
        #
        self.init_stats_tip()

    def browse_tmp(self):
        adir = tkFileDialog.askdirectory()
        if adir == '':
            return
        self._tmp_dir.set(adir)

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
            # download
            ifo = urllib2.urlopen(index_url, timeout=3)
            content = ifo.read()
            ifo.close()
            # write to local disk
            dst = os.path.join(cache_dir, Main.INDEX_FILE)
            ofo = open(dst, 'w')
            ofo.write(content)
            ofo.close()
            # fill in the listbox
            self.fill_in_listbox(index_url, content.split('\n'))
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
        #
        index_file = os.path.join(cache_dir, Main.INDEX_FILE)
        with open(index_file, 'r') as ifo:
            self.fill_in_listbox(index_url, ifo.readlines())

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
        self._stats.init_for_new_download(num)
        self.enable_stats_tip()
        #
        progress = 0
        jobs = []
        while self._running and progress < num:
            for i in jobs[:]:
                if i.isAlive():
                    continue
                sz = i.downloaded_size()
                if sz > 0:
                    # remove it from Listbox
                    content = self._segments.get(0, tk.END)
                    index = content.index(i._url)
                    self._segments.delete(index)
                jobs.remove(i)
                # report progress
                progress += 1
                self._msg_queue.put(progress)
                self._stats.update(sz)
            # if user changes settings of concurrent jobs
            slots = max(self._job_num.get() - len(jobs), 0)
            added = min(slots, self._job_queue.qsize())
            for i in range(0, added):
                ts = self._job_queue.get()
                job = Downloader(ts, cache)
                jobs.append(job)
                job.start()
        self._running = False
        self.disable_stats_tip()

    def listen_for_progress(self):
        """
        Update UI for downloading progress
        """
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
                tkMessageBox.showinfo(Main.WND_TITLE, 'All segments are downloaded.')

    def save_as(self):
        filename = tkFileDialog.asksaveasfilename(defaultextension='.mp4')
        if filename == '':
            return
        self._output.set(filename)

    def merge_cache(self):
        tmp = self._tmp_dir.get()
        if tmp == '':
            return
        out = self._output.get()
        if out == '':
            return
        #
        try:
            videos = [i for i in os.listdir(tmp) if i.endswith('.ts')]
            videos.sort()
            ofo = open(out, 'wb')
            os.chdir(tmp)
            for i in videos:
                ifo = open(i, 'rb')
                ofo.write(ifo.read())
                ifo.close()
            ofo.close()
            tkMessageBox.showinfo(Main.WND_TITLE, 'Merge is done.')
        except Exception as e:
            tkMessageBox.showerror(Main.WND_TITLE, str(e))

    def init_stats_tip(self):
        self._stats = DownloadStats(3)  # refresh data in every 3 seconds
        self._tip_text = tk.StringVar()

    def enable_stats_tip(self):
        self._tip_refresher = RepeatTimer(3.0, self.refresh_tip)
        self._tip_refresher.start()
        self._progressbar.bind('<Enter>', self.show_tip)
        self._progressbar.bind('<Leave>', self.hide_tip)

    def disable_stats_tip(self):
        self._progressbar.unbind('<Enter>')
        self._progressbar.unbind('<Leave>')
        self._tip_refresher.cancel()

    def realtime_tip(self):
        downloaded = self._stats.downloaded_size / 1024  # kilo-bytes
        if downloaded > 1024:
            downloaded = '%dMB' % (downloaded / 1024)    # mega-bytes
        else:
            downloaded = '%dKB' % downloaded
        speed = self._stats.speed / 1024  # KBps
        if speed > 1024:
            speed = '%.2fMBps' % (speed / 1024)  # MBps
        else:
            speed = '%.2fKBps' % speed
        remaining = self._stats.remaining_time
        if remaining < 60:  # seconds
            remaining = '%d seconds' % remaining
        elif remaining < 60 * 60:
            remaining = '%.2f minutes' % (remaining / 60.0)  # minutes
        else:
            remaining = '%.2f hours' % (remaining / 60.0 * 60.0)
        return 'Downloaded: %s\nSpeed: %s\nRemaining: %s' % (downloaded, speed, remaining)

    def refresh_tip(self):
        self._tip_text.set(self.realtime_tip())

    def show_tip(self, evt=None):
        self._tip_wnd = tk.Toplevel(self._progressbar)
        self._tip_wnd.wm_overrideredirect(True)  # remove window title bar
        label = tk.Label(self._tip_wnd, textvariable=self._tip_text, justify=tk.LEFT, bg='yellow')
        label.pack(ipadx=5)
        x, y = self._progressbar.winfo_rootx(), self._progressbar.winfo_rooty()
        w, h = label.winfo_reqwidth(), label.winfo_reqheight()
        sw, sh = label.winfo_screenwidth(), label.winfo_screenheight()
        offset = 20
        if x + w + offset > sw:
            x -= w + offset*2
        if y + h + offset > sh:
            y -= h + offset*2
        self._tip_wnd.wm_geometry("+%d+%d" % (x+offset, y+offset))

    def hide_tip(self, evt=None):
        self._tip_wnd.destroy()

    def delete_segments(self, evt):
        selected = self._segments.curselection()
        minimal = min(selected)
        maximal = max(selected)
        self._segments.delete(minimal, maximal)

    def fill_in_listbox(self, index_url, lines):
        """
        This part of code is tricky, because websites use disturbed URL in M3U8 file.
        """
        urls = []
        domain = url_domain(index_url)
        direct = url_directory(index_url)
        for line in lines:
            if line.startswith('#'):
                continue
            line = line.strip()
            if len(line) == 0:
                continue
            if line.find('://') > 0:  # full URL
                pass
            elif line.find('/', 1) == -1:  # basename
                line = url_join(direct, line)
            else:
                line = url_join(domain, line)
            urls.append(line)
        self._segments.delete(0, tk.END)
        self._segments.insert(tk.END, *urls)

    def clear_url(self, evt):
        self._url.set('')

if __name__ == '__main__':
    root = tk.Tk(className=Main.WND_TITLE)
    Main(root).pack(fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
    root.mainloop()
