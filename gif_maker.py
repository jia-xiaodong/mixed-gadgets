# -*- coding:utf-8 -*-

import os
import Tkinter as tk
import tkFileDialog
from PIL import Image, ImageSequence


class MainGUI(tk.Frame):
    def __init__(self, parent, *a, **kw):
        tk.Frame.__init__(self, parent, *a, **kw)
        #
        options_fill = {'expand': tk.YES, 'fill': tk.BOTH}
        options_fill_x = {'expand': tk.YES, 'fill': tk.X}
        self._image_list = []
        group = tk.LabelFrame(self, text='Image File List:', labelanchor=tk.N)
        group.pack(side=tk.TOP, **options_fill)
        self._filenames = tk.StringVar()
        tk.Listbox(group, listvariable=self._filenames, bd=0).pack(side=tk.TOP, **options_fill)
        frm = tk.Frame(group)
        frm.pack(side=tk.TOP, **options_fill)
        tk.Button(frm, text='Append Images', command=self.append_image).pack(side=tk.LEFT, **options_fill_x)
        tk.Button(frm, text='Clear', command=self.clear_list).pack(side=tk.LEFT, **options_fill_x)
        frm = tk.Frame(self)
        frm.pack(side=tk.TOP, **options_fill)
        tk.Button(frm, text='Save As', command=self.save_gif).pack(side=tk.LEFT)
        self._gif_name = tk.StringVar()
        tk.Entry(frm, textvariable=self._gif_name).pack(side=tk.LEFT, **options_fill_x)
        tk.Button(frm, text='Make GIF', command=self.make_gif).pack(side=tk.LEFT, **options_fill_x)
        self._gif_interval = tk.DoubleVar(value=0.0)
        options = {'from_': 0.0, 'to': 5.0, 'resolution': 0.1,
                   'label': 'interval (seconds)', 'variable': self._gif_interval,
                   'orient': tk.HORIZONTAL}
        tk.Scale(self, **options).pack(side=tk.LEFT, **options_fill_x)

    def append_image(self):
        extensions = tuple(Image.registered_extensions().keys())
        images = tkFileDialog.askopenfilename(filetypes=[('Image File', extensions)], multiple=True)
        if len(images) == 0:
            return
        #
        for i in images:
            if i in self._image_list:
                continue
            self._image_list.append(i)
        self._filenames.set(' '.join(os.path.basename(i) for i in self._image_list))

    def clear_list(self):
        self._filenames.set('')
        del self._image_list[:]

    def make_gif(self):
        filename = self._gif_name.get()
        if len(filename) == 0:
            return
        if len(self._image_list) < 2:
            return
        duration = self._gif_interval.get()
        if duration < 0.1:
            return
        images = [Image.open(i) for i in self._image_list]
        #
        # What will happen if one of images is GIF format?
        # .save() method can handle that case.
        # So I invoke it directly.
        # For detail see GifImagePlugin.py in PIL module.
        #
        # @param duration: millisecond.
        # @param disposal: 0~3.
        #    0: unspecified.
        #    1: do not dispose. Only update specified rectangle. Transparency shows old frame's content.
        #    2: replace with background color.
        #    3: replace with previous content.
        # @param transparency: integer. range unknown.
        # @param optimize: True | False. If palette is optimized to get rid of unused color entries.
        # @param loop: True | False.
        images[0].save(filename, save_all=True, append_images=images[1:], duration=duration*1000)

    def save_gif(self):
        filename = tkFileDialog.asksaveasfilename(defaultextension='.gif')
        if filename is '':
            return
        self._gif_name.set(filename)


def main():
    root = tk.Tk()
    root.title('GIF Maker')
    frm = MainGUI(root)
    frm.pack(expand=tk.YES, fill=tk.BOTH, padx=5, pady=5)
    root.mainloop()

if __name__ == '__main__':
    main()
