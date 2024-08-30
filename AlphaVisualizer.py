#!/usr/bin/env python3
# -*- coding:utf-8 -*-

from PIL import Image, ImageDraw, ImageTk
import os
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk


class MainFrame(tk.Frame):
    def __init__(self, master=None, *a, **kw):
        super(MainFrame, self).__init__(master, *a, **kw)
        #
        self.image_src_1 = None
        self.image_src_2 = None
        self.image_dst_1 = None  # must maintain a reference to display on Canvas
        self.image_dst_2 = None  # must maintain a reference to display on Canvas
        self.image_id_1 = 0
        self.image_id_2 = 0
        self.filename = None
        #
        frm = tk.Frame(self)
        frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
        self.canvas_1 = tk.Canvas(frm, bd=0, bg='#E4E4E4')
        self.canvas_1.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES)
        self.canvas_2 = tk.Canvas(frm, bd=0, bg='#E4E4E4')
        self.canvas_2.pack(side=tk.RIGHT, fill=tk.BOTH, expand=tk.YES)
        frm = tk.Frame(self)
        frm.pack(side=tk.TOP, fill=tk.X, expand=tk.NO)
        tk.Button(frm, text='Load Image', command=self.load_image).pack(side=tk.LEFT)
        self.image_info = tk.StringVar()
        tk.Label(frm, textvariable=self.image_info).pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        ttk.Sizegrip(self).pack(fill=tk.X, expand=tk.NO)
        #
        self.canvas_1.bind('<Configure>', self.auto_resize)
        self.canvas_1.bind('<Motion>', self.on_mouse_move)  # <B1-Motion> is for Button-1 scrolling

    def load_image(self):
        options = {}
        if self.filename is not None:
            options['initialdir'] = os.path.dirname(self.filename)
        filename = filedialog.askopenfilename(**options)
        if len(filename) == 0:
            return
        try:
            self.image_src_1 = Image.open(filename)
            if self.image_src_1.mode == 'RGBA':
                alpha_channel = self.image_src_1.getchannel(3)  # 获取 alpha 通道
                self.image_src_2 = Image.new('L', self.image_src_1.size)
                self.image_src_2.putdata(list(alpha_channel.getdata()))
            else:
                self.image_src_2 = None
            self.auto_resize()
            self.filename = filename
        except Exception as e:
            print(e)

    def auto_resize(self, event=None):
        if not self.image_src_1:
            return
        #
        # resize outline
        canvas_size = (self.canvas_1.winfo_width(), self.canvas_1.winfo_height())
        src_size = self.image_src_1.size
        new_size = self.calc_fit_size(src_size, canvas_size)

        self.canvas_1.delete(self.image_id_1)
        self.image_dst_1 = ImageTk.PhotoImage(self.image_src_1.resize(new_size))
        self.image_id_1 = self.canvas_1.create_image(0, 0, anchor=tk.NW, image=self.image_dst_1)

        self.canvas_2.delete(self.image_id_2)
        self.image_dst_2 = ImageTk.PhotoImage(self.image_src_2.resize(new_size))
        self.image_id_2 = self.canvas_2.create_image(0, 0, anchor=tk.NW, image=self.image_dst_2)

    def calc_fit_size(self, old_size, canvas_size):
        old_w, old_h = old_size
        canvas_w, canvas_h = canvas_size
        new_w = canvas_w
        new_h = new_w * old_h // old_w
        if new_h > canvas_h:
            new_h = canvas_h
            new_w = new_h * old_w // old_h
        return new_w, new_h

    def on_mouse_move(self, event):
        if not self.image_src_1:
            return
        if not self.image_dst_1:
            return
        # display mouse position
        x, y = event.x, event.y
        ratio = float(self.image_src_1.width) / self.image_dst_1.width()
        x, y = int(round(x*ratio)), int(round(y*ratio))
        if x >= self.image_src_1.size[0]:
            x = self.image_src_1.size[0] - 1
        if y >= self.image_src_1.size[1]:
            y = self.image_src_1.size[1] - 1
        pixel = self.image_src_1.getpixel((x, y))
        hex_str = ''.join(f'{num:X}' for num in pixel)
        self.image_info.set(f'mode={self.image_src_1.mode}, ({x}, {y})={pixel} #{hex_str}')


if __name__ == '__main__':
    root = tk.Tk(className=' Alpha Visualizer')  # extra blank to fix lowercase caption
    frm = MainFrame(root)
    frm.pack(side=tk.TOP, fill=tk.BOTH, expand=tk.YES)
    root.mainloop()
