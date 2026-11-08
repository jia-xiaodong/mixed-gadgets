#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
A few tools are put together.
All are used to help maintain my Kindle PW2.

@author Jia Xiaodong
Wed, Mar 6, 2019
"""


try:
    import Tkinter as tk
    import ttk
    import tkFileDialog as filedialog
    import tkMessageBox as messagebox
except:
    import tkinter as tk
    from tkinter import filedialog
    from tkinter import messagebox
    from tkinter import ttk

from PIL import Image, ImageFilter, ImageTk
import os, shutil
import queue, threading
from sys import platform


class PhotoCrop(tk.Frame):
    """
    Kindle PW2 supports JPG screen-saver image (758x1024).
    """
    FORMATS = ('Black & White', 'GrayScale', '256-Color Palette', '8-bit RGB', '8-bit RGBA')
    FORMAT_ID = ['1', 'L', 'P', 'RGB', 'RGBA']
    EXTENSIONS = ('.bmp', '.gif', '.jpg', '.ppm', '.png')
    EXTENSION_ID = ['BMP', 'GIF', 'JPEG', 'PPM', 'PNG']

    def __init__(self, master, *args, **kwargs):
        self.image_src = None
        self.image_dst = None
        self.image_bg = None
        self.image_id = 0
        self.outline_id = 0
        self.outline_move = False
        self.outline_ratio = -1
        self.move_start = (0, 0)
        self.filename = None

        tk.Frame.__init__(self, master, *args, **kwargs)
        self.canvas = tk.Canvas(self, bd=0, bg='#E4E4E4')
        self.canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        frm = tk.Frame(self)
        frm.pack(side=tk.TOP, fill=tk.X, expand=tk.NO)
        tk.Button(frm, text='Load Image', command=self.load_image).pack(side=tk.LEFT)
        self.image_size = tk.StringVar(value='size: ? X ?')
        tk.Label(frm, textvariable=self.image_size).pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        self.mouse_pos = tk.StringVar()
        tk.Label(frm, textvariable=self.mouse_pos).pack(side=tk.LEFT)
        tk.Button(frm, text='Save Clip', command=self.save_clip).pack(side=tk.LEFT)
        self.export_format = tk.StringVar(value=PhotoCrop.FORMATS[1])  # GrayScale is default
        tk.OptionMenu(frm, self.export_format, *PhotoCrop.FORMATS).pack(side=tk.LEFT)
        self.extension = tk.StringVar(value=PhotoCrop.EXTENSIONS[2])
        tk.OptionMenu(frm, self.extension, *PhotoCrop.EXTENSIONS).pack(side=tk.LEFT)
        frm = tk.LabelFrame(self, text='Outline Frame')
        frm.pack(side=tk.TOP, fill=tk.X, expand=tk.NO, padx=5, pady=5)
        tk.Button(frm, text='Draw', command=self.draw_rect).pack(side=tk.LEFT)
        sub_frm = tk.Frame(frm)
        sub_frm.pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        sub_sub_frm = tk.Frame(sub_frm)
        sub_sub_frm.pack(side=tk.TOP, fill=tk.X, expand=tk.YES)
        tk.Label(sub_sub_frm, text='X,Y: (').pack(side=tk.LEFT)
        self.origin_x = tk.IntVar(value=0)
        self.origin_y = tk.IntVar(value=0)
        wrapper = self.register(self.validate_xy)
        tk.Entry(sub_sub_frm, textvariable=self.origin_x, width=5, validate='key', validatecommand=(wrapper, '%P')).\
            pack(side=tk.LEFT)
        tk.Label(sub_sub_frm, text=',').pack(side=tk.LEFT)
        tk.Entry(sub_sub_frm, textvariable=self.origin_y, width=5, validate='key', validatecommand=(wrapper, '%P')).\
            pack(side=tk.LEFT)
        tk.Label(sub_sub_frm, text='), WxH:').pack(side=tk.LEFT)
        self.rect_w = tk.IntVar(value=0)
        self.rect_h = tk.IntVar(value=0)
        tk.Entry(sub_sub_frm, textvariable=self.rect_w, width=5, validate='key', validatecommand=(wrapper, '%P')).\
            pack(side=tk.LEFT)
        lbl = tk.Label(sub_sub_frm, text='X')
        lbl.pack(side=tk.LEFT)
        lbl.bind('<Double-1>', self.exchange_wh)
        tk.Entry(sub_sub_frm, textvariable=self.rect_h, width=5, validate='key', validatecommand=(wrapper, '%P')).\
            pack(side=tk.LEFT)
        self.ratio_lock = tk.IntVar(value=0)
        tk.Checkbutton(sub_sub_frm, text='lock on scaling', variable=self.ratio_lock, command=self.lock_changed).\
            pack(side=tk.LEFT)
        sub_sub_frm = tk.Frame(sub_frm)
        sub_sub_frm.pack(side=tk.TOP, fill=tk.X, expand=tk.YES)
        tk.Label(sub_sub_frm, text='scale:').pack(side=tk.LEFT)
        self.outline_scale = tk.DoubleVar(value=1)
        tk.Scale(sub_sub_frm, orient=tk.HORIZONTAL, command=self.resize_outline, showvalue=tk.NO,\
                 from_=0.0, to=1.0, variable=self.outline_scale, resolution=0.01).\
            pack(fill=tk.X, expand=tk.YES, padx=5, pady=5)

        self.canvas.bind('<Configure>', self.auto_resize)
        self.canvas.bind('<Button-1>', self.outline_mouse_down)
        self.canvas.bind('<Motion>', self.outline_mouse_move)  # <B1-Motion> is for Button-1 scrolling
        self.canvas.bind('<ButtonRelease-1>', self.outline_mouse_up)

    def load_image(self):
        options = {}
        if self.filename is not None:
            options['initialdir'] = os.path.dirname(self.filename)
        filename = filedialog.askopenfilename(**options)
        if len(filename) == 0:
            return
        try:
            self.canvas.delete(tk.ALL)
            self.image_src = Image.open(filename)
            self.image_size.set('size: %s X %s' % (self.image_src.size[0], self.image_src.size[1]))
            self.auto_resize()
            # format
            format = PhotoCrop.EXTENSION_ID.index(self.image_src.format)
            if format > -1:
                self.extension.set(PhotoCrop.EXTENSIONS[format])
            # mode
            mode = PhotoCrop.FORMAT_ID.index(self.image_src.mode)
            if mode > -1:
                self.export_format.set(PhotoCrop.FORMATS[mode])
        except Exception as e:
            print(e)
        else:
            self.filename = filename

    def auto_resize(self, event=None):
        if not self.image_src:
            return
        #
        # resize outline
        canvas_size = (self.canvas.winfo_width(), self.canvas.winfo_height())
        src_size = self.image_src.size
        new_size = self.calc_fit_size(src_size, canvas_size)
        if self.outline_exist():
            scale_ratio = float(new_size[0]) / self.image_dst.width()
            self.canvas.scale(self.outline_id, 0, 0, scale_ratio, scale_ratio)
        self.resize_image(new_size)
        self.canvas.tag_raise(self.outline_id, self.image_id)

    def resize_image(self, new_size):
        self.image_bg = self.image_src.resize(new_size)
        box = None
        if self.outline_exist():
            coord = self.canvas.coords(self.outline_id)
            box = (coord[0], coord[1], coord[2]-coord[0], coord[3]-coord[1])
        self.draw_image(box)

    def calc_fit_size(self, old_size, canvas_size):
        old_w, old_h = old_size
        canvas_w, canvas_h = canvas_size
        new_w = canvas_w
        new_h = new_w * old_h // old_w
        if new_h > canvas_h:
            new_h = canvas_h
            new_w = new_h * old_w // old_h
        return new_w, new_h

    def draw_rect(self):
        if not self.image_src:
            return
        x,y,w,h = self.origin_x.get(), self.origin_y.get(), self.rect_w.get(), self.rect_h.get()
        # x y w h is in coordinate space of the original image.
        # They should be mapped to canvas coordinate system.
        ratio = float(self.image_dst.width()) / self.image_src.width
        x,y,w,h = int(round(x*ratio)), int(round(y*ratio)), int(round(w*ratio)), int(round(h*ratio))
        if w == 0 or h == 0:
            return
        #
        # Delete previous outline if exists.
        self.canvas.delete(self.outline_id)
        #
        # draw mask
        self.draw_image((x, y, w, h))
        self.outline_id = self.canvas.create_rectangle(x, y, x+w, y+h, dash=(2,3), outline='#f0f0f0')
        #
        # calculate scale factor
        canvas_w, canvas_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        f0, f1 = float(w) / canvas_w, float(h) / canvas_h
        self.outline_scale.set(max(f0, f1))

    def save_clip(self):
        if not self.image_src:
            return
        try:
            x,y,w,h = self.origin_x.get(), self.origin_y.get(), self.rect_w.get(), self.rect_h.get()
            if x > self.image_src.width:
                return
            if y > self.image_src.height:
                return
            if x < 0:
                x = 0
            if w <=0:
                w = self.image_src.width
            if x+w > self.image_src.width:
                w = self.image_src.width - x
            if y < 0:
                y = 0
            if h <= 0:
                h = self.image_src.height
            if y+h > self.image_src.height:
                h = self.image_src.height - y

            heading, extension = os.path.splitext(self.filename)
            if len(self.extension.get()) > 0:
                extension = self.extension.get()
            filename = filedialog.asksaveasfilename(initialfile=os.path.basename(heading), defaultextension=extension)
            if len(filename) == 0:
                return
            clip = self.image_src.crop((x, y, x+w, y+h))
            mode = PhotoCrop.FORMATS.index(self.export_format.get())
            mode = PhotoCrop.FORMAT_ID[mode]
            if clip.mode != mode:
                clip = clip.convert(mode)
            clip.save(filename)
            clip.close()
        except Exception as e:
            print(e)

    def validate_xy(self, s):
        return all(map(lambda i: i.isdigit(), s))

    def resize_outline(self, ratio):
        coord = self.canvas.coords(self.outline_id)
        if len(coord) < 4:
            return
        if self.rect_w.get() == 0:
            return
        if self.rect_h.get() == 0:
            return
        #
        # 1. scale outline
        x0,y0,x1,y1 = coord
        canvas_w, canvas_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        factor = self.outline_scale.get()
        dx, dy = canvas_w * factor, canvas_h * factor
        if not self.ratio_lock.get():
            self.outline_ratio = float(self.rect_w.get()) / self.rect_h.get()
        if dx < dy:
            dy = dx / self.outline_ratio
        else:
            dx = dy * self.outline_ratio
        self.canvas.coords(self.outline_id, x0, y0, x0 + dx, y0 + dy)
        #
        # 2. redraw mask image
        self.draw_image((x0, y0, dx, dy))
        self.canvas.tag_raise(self.outline_id, self.image_id)
        #
        # 3. update control accordingly
        ratio = float(self.image_src.width) / self.image_dst.width()
        img_x = int(round(dx * ratio))
        img_y = int(round(dy * ratio))
        self.rect_w.set(img_x)
        self.rect_h.set(img_y)

    def outline_mouse_down(self, event):
        if not self.outline_exist():
            return
        box = self.canvas.coords(self.outline_id)
        x, y = event.x, event.y
        if box[0] <= x <= box[2] and box[1] <= y <= box[3]:
            self.move_start = (x, y)
            self.outline_move = True

    def outline_mouse_up(self, event):
        self.outline_move = False

    def outline_mouse_move(self, event):
        if not self.image_src:
            return
        if not self.image_dst:
            return
        # display mouse position
        x, y = event.x, event.y
        ratio = float(self.image_src.width) / self.image_dst.width()
        self.mouse_pos.set('%s, %s' % (int(round(x*ratio)), int(round(y*ratio))))
        #
        if self.outline_move:
            # move outline
            d0, d1 = x - self.move_start[0], y - self.move_start[1]
            self.canvas.move(self.outline_id, d0, d1)
            self.move_start = (x, y)
            # update control accordingly
            coord = self.canvas.coords(self.outline_id)
            img_x, img_y = int(round(coord[0] * ratio)), int(round(coord[1] * ratio))
            self.origin_x.set(img_x)
            self.origin_y.set(img_y)
            # redraw mask image
            self.draw_image((coord[0], coord[1], coord[2]-coord[0], coord[3]-coord[1]))
            self.canvas.tag_raise(self.outline_id, self.image_id)

    def draw_image(self, box=None):
        """
        @param box: (left, top, width, height) - highlight region with a transparent mask
        """
        # Canvas bug: it can't scale drawn image.
        # So delete it before re-draw an image
        self.canvas.delete(self.image_id)
        # [bug-fix] Mac Canvas doesn't support RGBA
        if platform.startswith('darwin') and 'A' in Image.getmodebandnames(self.image_bg.mode):
            bg_color = self.winfo_rgb(self.canvas['bg'])
            bg_color = tuple([i * 255 / 65535 for i in bg_color])
            bg_image = Image.new('RGB', self.image_bg.size, color=bg_color)
            bg_image.paste(self.image_bg, mask=self.image_bg)
        else:
            bg_image = self.image_bg.copy()
        # draw a black mask over image
        if box:
            box = [int(round(f)) for f in box]
            mask = Image.new('L', self.image_bg.size, 210)  # 0 means keeping original; 255 means total black
            mask.paste(0, (box[0],box[1],box[0]+box[2], box[1]+box[3]))
            bg_image.paste(0, mask=mask)
        self.image_dst = ImageTk.PhotoImage(bg_image)
        self.image_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.image_dst)

    def outline_exist(self):
        return self.canvas.type(self.outline_id) is not None

    def exchange_wh(self, event=None):
        w, h = self.rect_w.get(), self.rect_h.get()
        self.rect_w.set(h)
        self.rect_h.set(w)

    def lock_changed(self):
        try:
            if self.ratio_lock.get():
                self.outline_ratio = float(self.rect_w.get()) / self.rect_h.get()
        except:
            self.outline_ratio = -1


class SdrClean(tk.Frame):
    """
    Kindle system doesn't delete .sdr folders.
    Generally I have to delete them manually.
    This tool can detect redundant .sdr folders (and delete them).
    """
    STR_EMPTY = '<Empty>'
    STR_CLEAR = '<Clear>'
    STR_QUIZ = "<Is it a Kindle document folder?>"

    def __init__(self, master, *args, **kwargs):
        tk.Frame.__init__(self, master, *args, **kwargs)
        self.listbox = tk.Listbox(self)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        fm = tk.Frame(self)
        fm.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        tk.Button(fm, text='Specify Document  Folder', command=self.specify_folder).\
            pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        tk.Button(fm, text='Exempt One Item', command=self.exempt_item).\
            pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        tk.Button(fm, text='Delete All Folders', command=self.remove_all).\
            pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)

        self.listbox_show_empty()
        self._dir = None

    def specify_folder(self):
        dir = filedialog.askdirectory()
        if len(dir) == 0:
            return
        self._dir = dir
        files_and_dirs = os.listdir(dir)
        os.chdir(dir)
        all_files = [os.path.splitext(f)[0] for f in files_and_dirs if os.path.isfile(f)]
        all_dirs = [d[:-4] for d in files_and_dirs if d.endswith('.sdr')]
        danglings = [d for d in all_dirs if d not in all_files]
        self.listbox.delete(0, tk.END)
        if len(danglings) > 0:
            danglings.sort()
            for dangling in danglings:
                self.listbox.insert(tk.END, dangling)
        elif len(all_dirs) > 0: # no dangling .sdr folder, but it's kindle document indeed.
            self.listbox_show_clear()
        else:
            self.listbox_show_quiz()

    def remove_all(self):
        if not self.is_sdr_list():
            return
        try:
            for dangling in self.listbox.get(0, tk.END):
                shutil.rmtree('%s.sdr' % dangling)
            self.listbox.delete(0, tk.END)
            self.listbox_show_clear()
        except Exception as e:
            self.listbox_show_error(str(e))

    def exempt_item(self):
        if not self.is_sdr_list():
            return
        self.listbox.delete(tk.ACTIVE)
        if self.listbox.size() == 0:
            self.listbox_show_empty()

    def listbox_show_empty(self):
        self.listbox.insert(tk.END, SdrClean.STR_EMPTY)
        self.listbox.itemconfig(tk.END, background='green')

    def listbox_show_quiz(self):
        self.listbox.insert(tk.END, SdrClean.STR_QUIZ)
        self.listbox.itemconfig(tk.END, background='red')

    def listbox_show_error(self, s):
        self.listbox.insert(tk.END, s)
        self.listbox.itemconfig(tk.END, background='red')

    def listbox_show_clear(self):
        self.listbox.insert(tk.END, SdrClean.STR_CLEAR)
        self.listbox.itemconfig(tk.END, background='green')

    def is_sdr_list(self):
        sdr = self.listbox.get(tk.ACTIVE)
        reserved = (SdrClean.STR_EMPTY, SdrClean.STR_CLEAR, SdrClean.STR_QUIZ)
        return sdr not in reserved


class PhotoGrey(tk.Frame):
    """
    Kindle PW2 supports only greyscale images.
    So I made this tool to convert images on batch.
    """
    PROGRESS_MAX = 100

    def __init__(self, master, *a, **kw):
        tk.Frame.__init__(self, master, *a, **kw)
        frm = tk.Frame(self)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        tk.Label(frm, text='dir:').pack(side=tk.LEFT)
        self.dir = tk.StringVar()
        tk.Entry(frm, textvariable=self.dir).pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        tk.Button(frm, text='Browse', command=self.browse_dir).pack(side=tk.LEFT)
        frm = tk.Frame(self)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)
        self.progress = tk.IntVar(value=0)
        ttk.Progressbar(frm, mode='determinate', orient=tk.HORIZONTAL, variable=self.progress).\
            pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        self.btn = tk.Button(frm, text='Start', command=self.convert)
        self.btn.pack(side=tk.LEFT)

        # message queue between UI thread and worker thread
        self.thread_queue = None

    def browse_dir(self):
        name = filedialog.askdirectory()
        if len(name) == 0:
            return
        self.dir.set(name)

    def convert(self):
        dir = self.dir.get()
        if len(os.listdir(dir)) == 0:
            messagebox.showwarning('Greyscale', 'No images found!')
            return

        self.progress.set(0)
        self.btn.config(state=tk.DISABLED)
        self.thread_queue = Queue.Queue()  # used to communicate between main thread (UI) and worker thread
        threading.Thread(target=self.worker_thread, kwargs={'dir': dir}).start()
        self.after(100, self.listen_for_progress)

    def worker_thread(self, dir):
        os.chdir(dir)
        all_images = os.listdir(dir)
        progress = 0
        if not os.path.exists('output'):
            os.mkdir('output')

        step = PhotoGrey.PROGRESS_MAX / len(all_images)
        for i, each in enumerate(all_images, start=1):
            PhotoGrey.convert2greyscale(each, 'output')
            progress = i * step
            self.thread_queue.put(progress)
        if progress < PhotoGrey.PROGRESS_MAX:
            self.thread_queue.put(PhotoGrey.PROGRESS_MAX)

    def listen_for_progress(self):
        try:
            progress = self.thread_queue.get(False)
            self.progress.set(progress)
        except Queue.Empty: # must exist to avoid trace-back
            pass
        finally:
            if self.progress.get() < PhotoGrey.PROGRESS_MAX:
                self.after(100, self.listen_for_progress)
            else:
                self.btn.config(state=tk.NORMAL)
                messagebox.showinfo('Photo Tool', 'All work is done.')
                self.progress.set(0)

    @staticmethod
    def convert2greyscale(img, folder):
        try:
            src = Image.open(img)
            dst = src.convert('L')
            name, ext = os.path.splitext(img)
            output = os.path.join(folder, name+'.jpg')
            dst.save(output, 'JPEG', bits=8)
        except Exception as e:
            print('[%s] %s' % (img, str(e)))


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


def unit_test(cls, title):
    root = tk.Tk(className=' Photo Cropper') # extra blank to fix lowercase caption
    cls(root).pack(fill=tk.BOTH, expand=tk.YES)
    root.mainloop()


def unit_test_tabbar():
    root = tk.Tk(className=' Home Brew Kindle Toolkit') # extra blank to fix lowercase caption
    frm = TabBarFrame(root)
    frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
    frm.add(PhotoCrop(frm), 'Photo Clipper')
    frm.add(PhotoGrey(frm), 'Greyscale Photo Batch Converter')
    frm.add(SdrClean(frm), 'Clean Sdr Folder')
    root.mainloop()


def tmp():
    dir = '/Users/xiaodong/Desktop/kou'
    os.chdir(dir)
    all_images = [i for i in os.listdir(dir) if i.endswith('.jpg')]
    if not os.path.exists('output'):
        os.mkdir('output')

    box = (167, 0, 1167, 750)
    for i in all_images:
        im = Image.open(i)
        im2 = im.crop(box)
        im2.save('output/' + i)
        im.close()

if __name__ == "__main__":
    #unit_test(PhotoCrop, ' Photo Cropper')
    #unit_test(SdrClean, ' SDR Folder Cleaner')
    #unit_test(PhotoGrey, ' Photo Greyscaler')
    unit_test_tabbar()
    #tmp()
