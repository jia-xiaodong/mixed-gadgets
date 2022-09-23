#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import subprocess
import threading
import os.path
import tkinter as tk
from tkinter import messagebox


class MainUI(tk.Tk):
    def __init__(self, cmd):
        tk.Tk.__init__(self)
        self._output = tk.StringVar(value='Please wait...')
        tk.Label(self, textvariable=self._output).pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        self._is_stop = False
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW)  # hide console window
        threading.Thread(target=self.wait_result).start()

    def on_closing(self):
        if self._is_stop or messagebox.askokcancel('Quiz', 'Are you sure to exit?'):
            self._is_stop = True
            self._proc.kill()
            self.destroy()

    def wait_result(self):
        """update UI after sub-process finishes"""
        while not self._is_stop:
            try:
                out, err = self._proc.communicate(timeout=1)
                self._output.set(out)
                self._is_stop = True
            except subprocess.TimeoutExpired:
                pass


def main():
    parser = argparse.ArgumentParser(description='xxx')
    parser.add_argument('-c', '--cmd')  # publish platforms
    parser.add_argument('-x', '--pos_x')  # screen position x
    parser.add_argument('-y', '--pos_y')  # screen position y
    args, unknown_args = parser.parse_known_args()
    # args, unknown_args = parser.parse_known_args(['-c', 'C:\\Program Files (x86)\\Microsoft Visual Studio\\Installer\\resources\\app\\layout\\handle.exe',
    #                           '-a',   # Dump all handle information
    #                           '-u',   # Show the owning user name
    #                           'D:\\Books\\manual\\python378.chm'])

    if args.cmd is None:
        return

    cmdline = [args.cmd]
    cmdline.extend(unknown_args)
    root = MainUI(cmdline)
    if args.pos_x is not None and args.pos_y is not None:
        try:
            x = float(args.pos_x)
            y = float(args.pos_y)
            root.geometry('+%d+%d' % (x, y))
        except:
            pass
    root.title(os.path.basename(args.cmd))
    root.mainloop()


if __name__ == '__main__':
    main()
