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
        Update when every blocks is done with downloading.
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


class ThreadDownloader(threading.Thread):
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
            if self.file_exists(content):
                return
            with open(self._dst, 'wb') as ofo:
                ofo.write(content)
        except Exception as e:
            print('%s: %s' % (self._url, e))

    def downloaded_size(self):
        return self._size

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
        lbl.bind('<Double-Button-1>', self.onclick_clear_url)
        self._url = tk.StringVar()
        tk.Entry(frame, textvariable=self._url).pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
        btn = tk.Button(frame, text='Download', command=self.onclick_download_index_file)  # download m3u8 file (index file)
        btn.pack(side=tk.LEFT)
        # row 2 -- step 1
        frame = tk.Frame(group)
        frame.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        tk.Label(frame, text='Local Dir: ').pack(side=tk.LEFT)
        self._tmp_dir = tk.StringVar()
        tk.Entry(frame, textvariable=self._tmp_dir).pack(side=tk.LEFT, expand=tk.YES, fill=tk.X)
        tk.Button(frame, text='Browse', command=self.onclick_browse_tmp).pack(side=tk.LEFT)
        # step 2
        group = tk.LabelFrame(self, text='Step 2: Segments')
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
        xscroll.pack(side=tk.TOP, expand=tk.YES, fill=tk.X)
        self._segments['xscrollcommand'] = xscroll.set
        self._segments.bind('<Key-Delete>', self.onkey_tree_delete)
        self._segments.heading('sn', text='SN')
        self._segments.heading('url', text='URL')  # '#0' column is icon and it's hidden here
        self._segments.heading('state', text='State')    # we only need two columns: '#1' and '#2'
        self._segments.column('sn', width=30, stretch=False)
        self._segments.column('state', width=50, stretch=False, anchor=tk.CENTER)
        # row 2 -- step 2
        frame = tk.Frame(group)
        frame.pack(side=tk.TOP, expand=tk.YES, fill=tk.BOTH)
        tk.Button(frame, text='Read Local M3U8 File', command=self.onclick_load_index_file).pack(side=tk.LEFT)
        tk.Label(frame, text='Threads: ').pack(side=tk.LEFT)
        self._job_num = tk.IntVar()
        tk.Spinbox(frame, textvariable=self._job_num, from_=1, to=10, width=2).pack(side=tk.LEFT)
        self._btn = tk.Button(frame, text='Download', command=self.onclick_download_segments)
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
        tk.Button(frame, text='Browse', command=self.onclick_save_as).pack(side=tk.LEFT)
        tk.Button(frame, text='Merge', command=self.onclick_merge).pack(side=tk.LEFT)
        #
        self.init_stats_tip()

    def onclick_browse_tmp(self):
        adir = tkFileDialog.askdirectory()
        if adir == '':
            return
        self._tmp_dir.set(adir)

    def onclick_download_index_file(self):
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
            self.fill_in_listbox(index_url, content.split('\n'))
        except Exception as e:
            print(e)

    def onclick_load_index_file(self):
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

    def onclick_download_segments(self):
        urls = self._segments.get_children()
        if len(urls) == 0:
            return
        #
        if self._running:
            self._running = False   # global signal to stop running jobs
            self._btn.config(text='Download')
            return
        self._running = True
        self._btn.config(text='Cancel')
        try:
            self.clear_queue()
            for i in urls:
                self._job_queue.put(i)
            #
            self._progress.set(0)
            self._progressbar.config(maximum=len(urls))
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
                self._stats.update(sz)
                # visualize task state: completion or failure
                if sz > 0:
                    self._segments.delete(i.iid)
                else:
                    self._segments.set(i.iid, column='state', value='X')
                # no matter if download is successful, remove job from
                jobs.remove(i)
                # report progress
                progress += 1
                self._msg_queue.put(progress)
            # if user changes settings of concurrent jobs
            free_slots = max(self._job_num.get() - len(jobs), 0)
            added = min(free_slots, self._job_queue.qsize())
            for i in range(0, added):
                iid = self._job_queue.get()
                #  [ Important Point about ttk.Treeview ]
                # no matter what type it was when inserted into 'values',
                # it is str of type now when being retrieved.
                #
                # In short, be careful of below 'sn'
                sn, url, state = self._segments.item(iid, 'values')
                dst = os.path.join(cache, 'out%04d.ts' % int(sn))
                job = ThreadDownloader(url, dst)
                job.iid = iid  # attach a temporary attribute
                jobs.append(job)
                job.start()
                self._segments.set(iid, column='state', value='...')
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

    def onclick_save_as(self):
        filename = tkFileDialog.asksaveasfilename(defaultextension='.mp4')
        if filename == '':
            return
        self._output.set(filename)

    def onclick_merge(self):
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

    def onkey_tree_delete(self, evt):
        if self._running:  # keep treeview items intact when downloading
            return
        selected = self._segments.selection()
        # only unassigned job can be deleted
        unassigned = [i for i in selected if self._segments.item(i, 'values')[2] == '']
        self._segments.delete(*selected)

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
        self._segments.delete(*self._segments.get_children())
        for i, url in enumerate(urls, start=1):
            iid = 'I%04d' % i
            self._segments.insert('', tk.END, iid=iid, values=(i, url, ''))

    def onclick_clear_url(self, evt):
        self._url.set('')

if __name__ == '__main__':
    root = tk.Tk()
    root.title(Main.WND_TITLE)
    Main(root).pack(fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
    root.mainloop()
