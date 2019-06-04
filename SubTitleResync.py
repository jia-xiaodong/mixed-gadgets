#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
  Resynchronize subtitles for specified range.
  Only SRT and ASS format supported at present.

  Jia Xiaodong
  2016.05.14: srt format
  2018.09.14: ass format, file encoding detection
  tested against Python 2.7 on Windows/Mac OSX
"""

import logging
import Tkinter as tk, ttk
import tkFileDialog, tkMessageBox
import datetime
import re
import codecs, io

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', datefmt='%H:%M:%S', level=logging.INFO)

class SubtitleItem(object):
    def __init__(self):
        """
        contains a subtitle (can be multi-lined by '\n') and its start time and end time (precision of millisecond)
        """
        self.time_start = self.time_end = None

    @property
    def ts(self):
        return self.time_start, self.time_end

    def delay(self, value):
        """
        @param value: is object of datetime.timedelta
        """
        self.time_start += value
        self.time_end += value


class Formatter(object):
    def __init__(self):
        self.subtitles = []

    def parse(self):
        self.subtitles = []

    def shift_ts(self, frm, to, shift):
        for i in range(frm - 1, to):
            self.subtitles[i].delay(shift)

    def remove_sub(self, frm, to):
        self.subtitles = self.subtitles[:frm - 1] + self.subtitles[to:]

    def save(self, filename, encoding='utf-8'):
        pass

    def subtitles_count(self):
        return len(self.subtitles)

    @staticmethod
    def write_file_bom(fo, encoding):
        for bom, encodings in\
            (codecs.BOM_UTF8,     ('utf-8-sig',)),\
            (codecs.BOM_UTF16_LE, ('utf-16', 'utf-16-le')),\
            (codecs.BOM_UTF16_BE, ('utf-16-be',)):
            if any(e == encoding for e in encodings):
                fo.write(bom)
                return

    @staticmethod
    def detect_encoding_by_bom(bytes):
        for enc,boms in \
            ('utf-8-sig', (codecs.BOM_UTF8,)),\
            ('utf-32', (codecs.BOM_UTF32_LE,codecs.BOM_UTF32_BE)),\
            ('utf-16', (codecs.BOM_UTF16_LE,codecs.BOM_UTF16_BE)):
            if any(bytes.startswith(bom) for bom in boms):
                return enc
        return None

    @staticmethod
    def encode(s, encoding='utf-8'):
        if encoding=='utf-16':
            encoding = 'utf-16le'
        return s.encode(encoding=encoding)


class SrtSubtitleItem(SubtitleItem):
    SUB_NO = 0
    SUB_TS = 1
    SUB_TXT = 2

    def __init__(self):
        super(SrtSubtitleItem, self).__init__()
        self.subtitle = ''

    @property
    def sub(self):
        return self.subtitle

    def set_ts(self, value, handle):
        self.time_start, self.time_end = handle(value)

    def set_sub(self, value):
        """
        can be multi-lined by appending another line of subtitle
        @param value: a new line of subtitle
        """
        self.subtitle += value

    @property
    def pure_sub(self):
        return self.subtitle


class SrtFormatter(Formatter):
    TIME_FORMAT = None

    def parse(self, lines):
        super(SrtFormatter, self).parse()

        patt_line_no = re.compile(r'\d+')
        patt_timestamp = re.compile(r'\d{2}:\d{2}:\d{2}')

        step = SrtSubtitleItem.SUB_NO
        for line in lines:
            if step == SrtSubtitleItem.SUB_NO:
                if patt_line_no.search(line):
                    step = SrtSubtitleItem.SUB_TS
            elif step == SrtSubtitleItem.SUB_TS:
                result = patt_timestamp.findall(line)
                if len(result) == 2:
                    subtitle = SrtSubtitleItem()
                    subtitle.set_ts(line.rstrip('\r\n'), SrtFormatter.time_from_str)
                    step = SrtSubtitleItem.SUB_TXT
                else:
                    raise ValueError('Subtitle format error')
            elif step == SrtSubtitleItem.SUB_TXT:
                if len(line.rstrip('\r\n')) > 0:
                    subtitle.set_sub(line)
                else:
                    self.subtitles.append(subtitle)
                    step = SrtSubtitleItem.SUB_NO

    def save(self, filename, encoding='utf-8'):
        all_lines = []
        for i, subtitle in enumerate(self.subtitles):
            all_lines.append(Formatter.encode('%d\r\n' % (i + 1), encoding))
            all_lines.append(Formatter.encode(SrtFormatter.time_to_str(*subtitle.ts), encoding))
            all_lines.append(Formatter.encode(subtitle.sub, encoding))
            all_lines.append(Formatter.encode('\r\n', encoding))
        with open(filename, 'w') as fo:
            Formatter.write_file_bom(fo, encoding)
            fo.writelines(all_lines)

    # separator
    @staticmethod
    def sep():
        return ' --> '

    @staticmethod
    def time_from_str(time_str):
        """
        @param time_str: time string, which format is like '00:00:16,660 --> 00:00:19,630'
        """
        (start, _, end) = time_str.partition(SrtFormatter.sep())
        if not SrtFormatter.TIME_FORMAT:
            decimal = re.search('[\.,]', start).group(0)
            SrtFormatter.TIME_FORMAT = '%%H:%%M:%%S%s%%f' % decimal
        time_start = datetime.datetime.strptime(start + '000', SrtFormatter.TIME_FORMAT)
        time_end = datetime.datetime.strptime(end + '000', SrtFormatter.TIME_FORMAT)
        return time_start, time_end

    @staticmethod
    def time_to_str(start, end):
        """
        @param start:
        @param end: are datetime objects
        @return: a string can be written to file
        """
        time_start = start.strftime(SrtFormatter.TIME_FORMAT)[:-3] # microsecond -> millisecond
        time_end = end.strftime(SrtFormatter.TIME_FORMAT)[:-3]     # microsecond -> millisecond
        return '%s%s%s\r\n' % (time_start, SrtFormatter.sep(), time_end)


class AssSubtitleItem(SubtitleItem):
    indices = (0,0,0) # Start, End, Text
    rx = re.compile(r'({.+?})') # use non-greedy search pattern

    def __init__(self, fields):
        self.fields = fields
    @staticmethod
    def set_indices(i1, i2, i3):
        AssSubtitleItem.indices = (i1, i2, i3)
    def set_ts(self, handle):
        self.time_start = handle(self.fields[self.indices[0]])
        self.time_end = handle(self.fields[self.indices[1]])
    def update_ts(self, handle):
        self.fields[self.indices[0]] = handle(self.time_start)
        self.fields[self.indices[1]] = handle(self.time_end)
    @property
    def sub(self):
        return ','.join(self.fields)

    @property
    def pure_sub(self):
        text = self.fields[self.indices[2]]
        content = self.rx.sub(lambda match: '', text)
        return content.replace('\\N', '\n').rstrip()


class AssFormatter(Formatter):
    """
    Kodi-player supports below encoding:
      utf-16le (with BOM)
      utf-8 (without BOM)
      GB2312
    Kodi-player recognizes language by naming conventions:
      Chinese: *.chi.ass
      English: *.eng.srt
    It's ISO 639-2 language code.
    """
    DIALOG_FORMAT = None
    TIME_FORMAT_1 = '%H:%M:%S.%f'
    TIME_FORMAT_2 = '%-H:%M:%S.%f'  # Kodi Player can't recognize '00:01:59'. Leading zero must be stripped.

    def __init__(self):
        self.header = ''

    def parse(self, lines):
        super(AssFormatter, self).parse()
        SUB_HEAD = 0
        SUB_FORMAT = 1
        SUB_CONTENT = 2
        step = SUB_HEAD
        try:
            for i, line in enumerate(lines):
                if step == SUB_CONTENT:
                    if len(line) < len('Dialogue: '):
                        return
                    subtitle = AssSubtitleItem(line[len('Dialogue: '):].split(',', len(self.DIALOG_FORMAT)-1))
                    subtitle.set_ts(AssFormatter.time_from_str)
                    self.subtitles.append(subtitle)
                elif step == SUB_HEAD:
                    self.header += line
                    if line.startswith('[Events]'):
                        step = SUB_FORMAT
                elif step == SUB_FORMAT:
                    if line.startswith('Format:'):
                        step = SUB_CONTENT
                        self.DIALOG_FORMAT = line[len('Format: '):].split(', ')
                        mapping = dict(zip(self.DIALOG_FORMAT, range(len(self.DIALOG_FORMAT))))
                        start = mapping['Start']
                        end   = mapping['End']
                        keys  = filter(lambda key: key.startswith('Text'), self.DIALOG_FORMAT)
                        text  = mapping[keys[0]]
                        AssSubtitleItem.set_indices(start, end, text)
                    else:
                        raise Exception()
                else:  # error
                    raise Exception()
        except Exception as e:
            print('Line %d is wrong' % i+1)

    def shift_ts(self, frm, to, shift):
        super(AssFormatter, self).shift_ts(frm, to, shift)
        for i in range(frm - 1, to):
            self.subtitles[i].update_ts(AssFormatter.time_to_str)

    def save(self, filename, encoding='utf-8'):
        with open(filename, 'w') as fo:
            Formatter.write_file_bom(fo, encoding)
            fo.write(Formatter.encode(self.header, encoding))
            fo.write(Formatter.encode('Format: %s' % ', '.join(self.DIALOG_FORMAT), encoding))
            for subtitle in self.subtitles:
                fo.write(Formatter.encode('Dialogue: %s' % subtitle.sub, encoding))

    @staticmethod
    def time_from_str(time_str):
        """
        @param time_str: time string, which format is like '0:00:16.66'
        """
        return datetime.datetime.strptime(time_str + '0000', AssFormatter.TIME_FORMAT_1)

    @staticmethod
    def time_to_str(tm):
        """
        @param tm: is datetime object
        @return: a string can be written to file
        """
        return tm.strftime(AssFormatter.TIME_FORMAT_2)[:-4] # microsecond -> millisecond


class SubtitleFile:
    def __init__(self, filename, lines):
        self.filepath = filename
        formatter = None
        if filename.lower().endswith('srt'):
            formatter = SrtFormatter()
        elif filename.lower().endswith('ass'):
            formatter = AssFormatter()
        formatter.parse(lines)
        self.formatter = formatter

    @property
    def subtitles_count(self):
        return self.formatter.subtitles_count()

    def shift_ts(self, start, end, shift):
        """
        Shift time-stamps (ts)
        @param shift: number, positive means delay subtitles a few seconds; negative for the vice versa.
        @param start, end: subtitle's order (1 --> largest)
        """
        dt = datetime.timedelta(seconds=shift)
        self.formatter.shift_ts(start, end, dt)

    def remove_subtitles(self, start, end):
        """
        @param start: >= 1
        @param end: may equal to start
        """
        self.formatter.remove_sub(start, end)

    def get_sub(self, idx):
        return self.formatter.subtitles[idx].pure_sub

    def save(self, encoding):
        self.formatter.save(self.filepath, encoding)


class GUI(tk.Tk):
    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)

        ROW_SRT_PATH = 0
        ROW_RANGE_AND_TIME = 1
        ROW_START = 2
        ROW_PREVIEW = 3

        self.PLACE_HOLDER = "<file's path>"

        # make children widget are auto-resizable when window's size is changed
        self.rowconfigure(ROW_SRT_PATH, weight=1)
        self.rowconfigure(ROW_RANGE_AND_TIME, weight=2)
        self.rowconfigure(ROW_START, weight=2)
        self.rowconfigure(ROW_PREVIEW, weight=2)
        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=1)

        # application's whole path and extra parameters
        self.subtitle_filename = tk.StringVar(value=self.PLACE_HOLDER)
        ctrl = tk.Entry(self, textvariable=self.subtitle_filename)
        ctrl.grid(column=0, row=ROW_SRT_PATH, sticky=tk.NSEW, padx=5, pady=5)
        ctrl.bind('<FocusIn>', lambda e: self.toggle_placeholder(False))
        ctrl.bind('<FocusOut>', lambda e: self.toggle_placeholder(True))

        # open file dialog
        group = tk.Button(self, text='<--  Choose a Subtitle File', command=self.select_a_file)
        group.grid(column=1, row=ROW_SRT_PATH, sticky=tk.NSEW, padx=5, pady=5)

        # group a number of widgets together (targeted range)
        group = tk.LabelFrame(self, text="Option: Targeted Range")
        group.rowconfigure(0, weight=1)
        group.rowconfigure(1, weight=1)
        group.columnconfigure(0, weight=1)
        group.columnconfigure(1, weight=1)
        group.grid(column=0, row=ROW_RANGE_AND_TIME, sticky=tk.NSEW, padx=5, pady=5)

        #
        ctrl = tk.Label(group, text='begin from', justify=tk.LEFT)
        ctrl.grid(column=0, row=0, sticky=tk.NSEW, padx=5, pady=5)

        # input where to start
        self.start_number = tk.IntVar(value=1)
        ctrl = tk.Entry(group, justify=tk.CENTER, textvariable=self.start_number)
        ctrl.grid(column=1, row=0, sticky=tk.NSEW, padx=5, pady=5)

        ctrl = tk.Label(group, text='stop until', justify=tk.LEFT)
        ctrl.grid(column=0, row=1, sticky=tk.NSEW, padx=5, pady=5)

        # input where to stop
        self.stop_number = tk.IntVar(value=0)
        ctrl = tk.Entry(group, justify=tk.CENTER, textvariable=self.stop_number)
        ctrl.grid(column=1, row=1, sticky=tk.NSEW, padx=5, pady=5)

        # group a number of widgets together (how much time be shifted)
        group = tk.LabelFrame(self, text="Option: Time Shift")
        group.rowconfigure(0, weight=1)
        group.rowconfigure(1, weight=1)
        group.grid(column=1, row=ROW_RANGE_AND_TIME, sticky=tk.NSEW, padx=5, pady=5)

        # input how much time to shift
        self.shift_time = tk.DoubleVar(value=0)
        ctrl = tk.Entry(group, justify=tk.CENTER, textvariable=self.shift_time)
        ctrl.grid(row=0, sticky=tk.NSEW, padx=5, pady=5)

        #
        ctrl = tk.Label(group, text='Seconds (integer)')
        ctrl.grid(row=1, sticky=tk.NSEW, padx=5, pady=5)

        # group actions together
        group = tk.LabelFrame(self, text='Supported Actions')
        group.rowconfigure(0, weight=1)
        group.rowconfigure(1, weight=1)
        group.columnconfigure(0, weight=1)
        group.columnconfigure(1, weight=1)
        group.columnconfigure(2, weight=1)
        group.grid(column=0, row=ROW_START, sticky=tk.NSEW, padx=5, pady=5)

        #
        self.action = tk.IntVar()
        radio = tk.Radiobutton(group, text='Sync Timestamps', variable=self.action, value=0)
        radio.grid(column=0, columnspan=2, row=0, sticky=tk.N+tk.S+tk.W, padx=5, pady=5)
        radio = tk.Radiobutton(group, text='Remove Subtitles', variable=self.action, value=1)
        radio.grid(column=0, columnspan=2, row=1, sticky=tk.N+tk.S+tk.W, padx=5, pady=5)
        radio = tk.Radiobutton(group, text='Save File', variable=self.action, value=2)
        radio.grid(column=0, columnspan=2, row=2, sticky=tk.N+tk.S+tk.W, padx=5, pady=5)

        #
        ctrl = tk.Button(group, text='Start Action', command=self.start_action)
        ctrl.grid(column=2, row=0, rowspan=2, sticky=tk.NSEW, padx=5, pady=5)

        #
        group = tk.LabelFrame(self, text='Subtitle File Encoding')
        group.rowconfigure(0, weight=1)
        group.rowconfigure(1, weight=1)
        group.rowconfigure(2, weight=0)
        group.columnconfigure(0, weight=1)
        group.columnconfigure(1, weight=3)
        group.grid(column=1, row=ROW_START, sticky=tk.NSEW, padx=5, pady=5)

        self.file_encoding = tk.StringVar(value='File encoding: ?')
        ctrl = tk.Label(group, textvariable=self.file_encoding)
        ctrl.grid(row=0, columnspan=2, sticky=tk.N+tk.S+tk.W, padx=5, pady=5)
        ctrl = tk.Label(group, text='Save Encoding: ')
        ctrl.grid(row=1, column=0, sticky=tk.NSEW, padx=5, pady=5)
        encodings = ('utf-8', 'utf-16')  # both works well in KODI-player
        self.save_encoding = tk.StringVar(value=encodings[0])
        ctrl = tk.OptionMenu(group, self.save_encoding, *encodings)
        ctrl.grid(row=1, column=1, sticky=tk.NSEW, padx=5, pady=5)
        tk.Button(group, text='About Kodi Player', command=lambda : tkMessageBox.showinfo('For the Record', '''
Kodi-player supports below encoding:
 -utf-16le (with BOM)
 -utf-8 (without BOM)
 -GB2312
Kodi-player recognizes language by naming conventions like these:
 -Chinese: *.chi.ass
 -English: *.eng.srt
It's ISO 639-2 language code.
        ''')).grid(row=2, column=0)

        #
        group = tk.LabelFrame(self, text='Subtitle Preview')
        group.rowconfigure(0, weight=1)
        group.rowconfigure(1, weight=1)
        group.columnconfigure(0, weight=1)
        group.grid(row=ROW_PREVIEW, columnspan=2, sticky=tk.NSEW, padx=5, pady=5)

        self.idx_selector = tk.Scale(group, showvalue=1, orient=tk.HORIZONTAL, command=self.scale_changed)
        self.set_scale(1, 10)
        self.idx_selector.grid(sticky=tk.NSEW)
        self.bind('<Left>', self.scale_dec)
        self.bind('<Right>', self.scale_inc)

        self.subtitle_text = tk.StringVar()
        ctrl = tk.Label(group, textvariable=self.subtitle_text, height=3, justify=tk.CENTER, bg='grey')
        ctrl.grid(sticky=tk.NSEW)

        #
        self.subtitle_nfo = None

    def select_a_file(self):
        filename = tkFileDialog.askopenfilename(filetypes=[('All files', '*'), ('srt', '.srt'), ('ass', '.ass')])
        if not filename:
            return
        try:
            with open(filename, 'r') as fo:
                raw = fo.read()
            encoding = Formatter.detect_encoding_by_bom(raw)
            if encoding:
                content = raw.decode(encoding=encoding)
            else:
                for enc in ['utf-8', 'utf-16', 'utf-32', 'gb2312', 'big5', 'big5hkscs', 'gbk', 'gb18030']:
                    try:
                        content = raw.decode(encoding=enc)
                        encoding = enc
                        break
                    except UnicodeDecodeError as e:
                        pass
                else:
                    raise Exception('UnicodeDecodeError', 'cannot decode file content')

            self.subtitle_filename.set(filename)
            self.file_encoding.set('File encoding: ' + encoding)
            self.subtitle_nfo = SubtitleFile(filename, content.splitlines(True))
            self.stop_number.set(self.subtitle_nfo.subtitles_count)
            self.start_number.set(1)
            self.shift_time.set(0)
            self.set_scale(1, self.subtitle_nfo.subtitles_count)
            self.scale_changed(1)
        except Exception as e:
            tkMessageBox.showerror('Unknown Decoding', 'Error: %s' % e)

    def start_action(self): 
        # check file existence
        try:
            if not self.subtitle_nfo:
                raise Exception('IO Error', 'No subtitle file specified')

            # check range validity
            begin = self.start_number.get()
            end = self.stop_number.get()
            if begin < 1 or end > self.subtitle_nfo.subtitles_count:
                raise Exception('Wrong Range', 'Check range.\r\nNotice file contains %d subtitles in total' % (
                    self.subtitle_nfo.subtitles_count))

            action = self.action.get()
            if action == 0:
                shift = self.shift_time.get()
                if shift == 0:
                    raise Exception('Wrong Shift', 'Check shift.\r\nShift can\'t be ZERO')
                self.subtitle_nfo.shift_ts(begin, end, shift)
            elif action == 1:
                self.subtitle_nfo.remove_subtitles(begin, end)
                self.set_scale(1, self.subtitle_nfo.subtitles_count)
            elif action == 2:
                self.subtitle_nfo.save(self.save_encoding.get())
        except ValueError as e:
            tkMessageBox.showerror('ValueError', "Error: {}".format(e.message))
        except Exception as e:
            tkMessageBox.showerror(e.args[0], e.args[1])
        else:
            tkMessageBox.showinfo('xxx', "Job's done")

    def set_scale(self, frm, to):
        self.idx_selector.configure(from_=frm, to=to, tickinterval=(to-frm)/4)
        self.idx_selector.set(1)

    def scale_changed(self, value):
        value = int(value)
        if not self.subtitle_nfo:
            self.subtitle_text.set('<< nothing >>')
        elif value <= self.subtitle_nfo.subtitles_count:
            txt = self.subtitle_nfo.get_sub(value-1)
            txt = txt.replace(u'\r\n', u'\n').rstrip()
            self.subtitle_text.set(txt)
        self.scale_value = value

    def scale_inc(self, event):
        if not self.subtitle_nfo:
            return
        if self.scale_value < self.subtitle_nfo.subtitles_count:
            self.idx_selector.set(self.scale_value+1)

    def scale_dec(self, event):
        if self.scale_value > 1:
            self.idx_selector.set(self.scale_value-1)

    def toggle_placeholder(self, show=True):
        filename = self.subtitle_filename.get()
        if show:
            if len(filename) == 0:
                self.subtitle_filename.set(self.PLACE_HOLDER)
        elif filename == self.PLACE_HOLDER:
            self.subtitle_filename.set('')

if __name__ == "__main__":
    gui = GUI(className=' Subtitle Resync Tool') # extra blank to avoid lowercase caption
    gui.mainloop()
    logging.info('Script is done executing.')