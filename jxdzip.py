"""Python 3 / Tkinter: custom three-byte ZIP header and optional traditional ZipCrypto password."""
import os
from pathlib import Path
import queue
import shutil
import tempfile
import threading
import struct
import time
import zipfile
import zlib
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

def _crc_table():
    table = []
    for value in range(256):
        for _ in range(8):
            value = (value >> 1) ^ (0xEDB88320 if value & 1 else 0)
        table.append(value)
    return table


_CRC_TABLE = _crc_table()


class ZipCrypto:
    """Traditional PKWARE encryption: weak legacy encryption, not AES."""
    def __init__(self, password):
        self.keys = [0x12345678, 0x23456789, 0x34567890]
        for value in password:
            self.update(value)

    def update(self, value):
        a, b, c = self.keys
        a = (a >> 8) ^ _CRC_TABLE[(a ^ value) & 255]
        b = ((b + (a & 255)) * 134775813 + 1) & 0xFFFFFFFF
        c = (c >> 8) ^ _CRC_TABLE[(c ^ (b >> 24)) & 255]
        self.keys = [a, b, c]

    def encrypt(self, data):
        result = bytearray(len(data))
        for index, value in enumerate(data):
            temp = self.keys[2] | 2
            result[index] = value ^ (((temp * (temp ^ 1)) >> 8) & 255)
            self.update(value)
        return result


def _write_encrypted_entry(source, writer, password):
    """Write one local entry and return its central-directory record."""
    name = source.name.encode("utf-8")
    if len(name) > 65535:
        raise ValueError("文件名过长")
    stamp = time.localtime(source.stat().st_mtime)
    year = min(2107, max(1980, stamp.tm_year))
    date = ((year - 1980) << 9) | (stamp.tm_mon << 5) | stamp.tm_mday
    clock = (stamp.tm_hour << 11) | (stamp.tm_min << 5) | (stamp.tm_sec // 2)
    flags, method = 0x0801, 8  # UTF-8 + encryption, no data descriptor
    crc, size = 0, 0
    with tempfile.TemporaryFile() as compressed:
        compressor = zlib.compressobj(wbits=-15)
        with source.open("rb") as reader:
            while True:
                data = reader.read(1024 * 1024)
                if not data:
                    break
                size += len(data)
                if size >= 0xFFFFFFFF:
                    raise ValueError("密码压缩暂不支持 ZIP64（文件必须小于 4 GiB）")
                crc = zlib.crc32(data, crc)
                compressed.write(compressor.compress(data))
        compressed.write(compressor.flush())
        packed_size = compressed.tell() + 12
        central_offset = writer.tell() + 30 + len(name) + packed_size
        if central_offset + 46 + len(name) + 22 >= 0xFFFFFFFF:
            raise ValueError("密码压缩包过大，暂不支持 ZIP64")
        compressed.seek(0)
        cipher = ZipCrypto(password.encode("utf-8"))
        local_offset = writer.tell()
        writer.write(struct.pack("<I5H3I2H", 0x04034B50, 20, flags, method,
                                 clock, date, crc, packed_size, size, len(name), 0))
        writer.write(name)
        writer.write(cipher.encrypt(os.urandom(11) + bytes([crc >> 24])))
        while True:
            data = compressed.read(1024 * 1024)
            if not data:
                break
            writer.write(cipher.encrypt(data))
        return (struct.pack("<I6H3I5H2I", 0x02014B50, 20, 20, flags, method,
                            clock, date, crc, packed_size, size, len(name),
                            0, 0, 0, 0, 0, local_offset) + name)


def write_password_zip(sources, destination, password):
    """Write multiple ZipCrypto entries; each has its own encryption state."""
    if len(sources) >= 65535:
        raise ValueError("密码压缩最多支持 65534 个文件（不支持 ZIP64）")
    with open(destination, "wb") as writer, tempfile.TemporaryFile() as central:
        for source in sources:
            central.write(_write_encrypted_entry(source, writer, password))
        central_offset = writer.tell()
        central_size = central.tell()
        if central_offset + central_size + 22 >= 0xFFFFFFFF:
            raise ValueError("密码压缩包过大，暂不支持 ZIP64")
        central.seek(0)
        shutil.copyfileobj(central, writer)
        writer.write(struct.pack("<I4H2IH", 0x06054B50, 0, 0, len(sources),
                                 len(sources), central_size, central_offset, 0))


def parse_header(value):
    try:
        header = bytes.fromhex(value)
    except ValueError:
        raise ValueError("文件头必须是十六进制，例如：41 42 43") from None
    if len(header) != 3:
        raise ValueError("文件头必须恰好为 3 个字节，例如：41 42 43")
    return header


def validate_name(name):
    """Reject unsafe or non-portable flat archive names."""
    if (not name or name in (".", "..") or any(c in name for c in '/\\:<>"|?*')
            or any(ord(c) < 32 for c in name) or name.endswith((".", " "))
            or name.split('.')[0].upper() in
            {"CON", "PRN", "AUX", "NUL", *("COM%d" % i for i in range(1, 10)),
             *("LPT%d" % i for i in range(1, 10))}):
        raise ValueError("压缩包包含不安全的文件名")


def compress_file(source, destination, header, password=""):
    """Accept a single path or a sequence of paths; archive names are basenames."""
    if isinstance(source, (str, os.PathLike)):
        source = [source]
    sources = [Path(item).resolve() for item in source]
    destination = Path(destination).resolve()
    if len(header) != 3:
        raise ValueError("文件头必须为 3 个字节")
    if not sources:
        raise ValueError("请至少选择一个文件")
    names = set()
    for item in sources:
        if not item.is_file():
            raise ValueError("源文件不存在或不是文件：" + str(item))
        if item == destination or (destination.exists() and os.path.samefile(item, destination)):
            raise ValueError("压缩包不能覆盖任何源文件")
        validate_name(item.name)
        key = item.name.casefold()
        if key in names:
            raise ValueError("存在同名文件，请重命名后再压缩：" + item.name)
        names.add(key)
    # 先完整写入临时文件，成功后才替换目标。
    fd, temporary = tempfile.mkstemp(dir=str(destination.parent), suffix=".tmp")
    os.close(fd)
    try:
        if password:
            write_password_zip(sources, temporary, password)
        else:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for item in sources:
                    archive.write(str(item), arcname=item.name)
        with open(temporary, "r+b") as stream:
            if stream.read(4) != b"PK\x03\x04":
                raise ValueError("生成的 ZIP 文件头异常")
            stream.seek(0)
            stream.write(header)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return str(destination)


def extract_file(source, output_directory, header, password=""):
    if len(header) != 3:
        raise ValueError("文件头必须为 3 个字节")
    output_directory = Path(output_directory).resolve()
    if not output_directory.is_dir():
        raise ValueError("请选择有效的输出目录")
    with open(source, "rb") as original, tempfile.TemporaryFile() as restored:
        if original.read(3) != header:
            raise ValueError("指定的 3 个字节与压缩包文件头不匹配")
        if original.read(1) != b"\x04":
            raise ValueError("文件不是本程序支持的压缩包")
        restored.write(b"PK\x03\x04")
        shutil.copyfileobj(original, restored)
        restored.seek(0)
        with zipfile.ZipFile(restored, "r") as archive:
            if password:
                archive.setpassword(password.encode("utf-8"))
            entries = archive.infolist()
            if not entries:
                raise ValueError("压缩包没有文件")
            names = set()
            for entry in entries:
                if entry.is_dir():
                    raise ValueError("本程序仅支持文件，不支持文件夹条目")
                if entry.compress_type == 99:
                    raise ValueError("标准库版本不支持旧版 AES 加密包，请先用旧版解压后重新压缩")
                validate_name(entry.filename)
                key = entry.filename.casefold()
                if key in names:
                    raise ValueError("压缩包包含重名文件：" + entry.filename)
                names.add(key)
            # 使用独立的新目录，避免覆盖已有文件。失败时清理部分结果。
            folder = Path(tempfile.mkdtemp(prefix="解压_", dir=str(output_directory)))
            try:
                for entry in entries:
                    with archive.open(entry, "r") as reader, open(folder / entry.filename, "xb") as writer:
                        shutil.copyfileobj(reader, writer)
            except Exception:
                shutil.rmtree(folder)
                raise
    return str(folder)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("自定义文件头 ZIP 压缩 / 解压")
        self.geometry("760x580")
        self.minsize(660, 540)
        self.events = queue.Queue()
        self.busy = False
        self.selected_files = []
        self.header = tk.StringVar(value="41 42 43")
        self.password = tk.StringVar()
        self.status = tk.StringVar(value="就绪")
        panel = ttk.Frame(self, padding=20)
        panel.pack(fill="both", expand=True)
        panel.columnconfigure(1, weight=1)
        panel.rowconfigure(4, weight=1)
        ttk.Label(panel, text="自定义文件头（3 字节，十六进制）").grid(row=0, column=0, sticky="w", pady=10)
        ttk.Entry(panel, textvariable=self.header).grid(row=0, column=1, sticky="ew", padx=10)
        ttk.Label(panel, text="例如：41 42 43 表示 ASCII 的 ABC；也支持 00 FF 80。").grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Label(panel, text="密码（留空表示不加密）").grid(row=2, column=0, sticky="w", pady=18)
        ttk.Entry(panel, textvariable=self.password, show="*").grid(row=2, column=1, sticky="ew", padx=10)
        ttk.Label(panel, text="要压缩的文件（可按 Ctrl / Shift 多选后删除）").grid(row=3, column=0, columnspan=2, sticky="w")
        files_panel = ttk.Frame(panel)
        files_panel.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        files_panel.rowconfigure(0, weight=1)
        files_panel.columnconfigure(0, weight=1)
        self.file_list = tk.Listbox(files_panel, selectmode=tk.EXTENDED, exportselection=False, height=7)
        self.file_list.grid(row=0, column=0, sticky="nsew")
        vertical_scroll = ttk.Scrollbar(files_panel, orient="vertical", command=self.file_list.yview)
        vertical_scroll.grid(row=0, column=1, sticky="ns")
        horizontal_scroll = ttk.Scrollbar(files_panel, orient="horizontal", command=self.file_list.xview)
        horizontal_scroll.grid(row=1, column=0, sticky="ew")
        self.file_list.configure(yscrollcommand=vertical_scroll.set, xscrollcommand=horizontal_scroll.set)
        file_buttons = ttk.Frame(panel)
        file_buttons.grid(row=5, column=0, columnspan=2, sticky="we", pady=8)
        self.add_button = ttk.Button(file_buttons, text="添加文件…", command=self.add_files)
        self.add_button.pack(side="left")
        self.remove_button = ttk.Button(file_buttons, text="删除文件", command=self.remove_files)
        self.remove_button.pack(side="left", padx=(10, 0))
        self.compress_button = ttk.Button(file_buttons, text="压缩文件…", command=self.compress)
        self.compress_button.pack(side="right", padx=(10, 0))
        ttk.Label(panel, text="压缩：添加文件到列表，再点击压缩并选择保存位置。\n解压：输入相同文件头和密码，选择压缩包及输出目录。\n解压结果放入新建子目录，不覆盖已有文件。\n密码使用传统 ZipCrypto（安全性较弱，不适合敏感数据）。", justify="left").grid(row=6, column=0, columnspan=2, sticky="w", pady=10)
        self.extract_button = ttk.Button(panel, text="解压文件…", command=self.extract)
        self.extract_button.grid(row=7, column=0, sticky="ew", padx=10)
        ttk.Label(panel, textvariable=self.status).grid(row=8, column=0, columnspan=2, sticky="w")
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self.poll)

    def add_files(self):
        if self.busy:
            return
        files = filedialog.askopenfilenames(title="选择要压缩的文件（支持多选）", parent=self)
        if not files:
            return
        existing = {os.path.normcase(path) for path in self.selected_files}
        for filename in files:
            path = str(Path(filename).resolve())
            key = os.path.normcase(path)
            if key not in existing:
                self.selected_files.append(path)
                self.file_list.insert(tk.END, path)
                existing.add(key)
        self.status.set(f"已选择 {len(self.selected_files)} 个文件")

    def remove_files(self):
        if self.busy:
            return
        for index in reversed(self.file_list.curselection()):
            del self.selected_files[index]
            self.file_list.delete(index)
        self.status.set(f"已选择 {len(self.selected_files)} 个文件")

    def settings(self):
        try:
            return parse_header(self.header.get()), self.password.get()
        except ValueError as exc:
            messagebox.showerror("输入错误", str(exc), parent=self)
            return None

    def compress(self):
        if self.busy:
            return
        if not self.selected_files:
            messagebox.showwarning("未选择文件", "请先点击“添加文件”选择要压缩的文件。", parent=self)
            return
        settings = self.settings()
        if settings is None:
            return
        source = tuple(self.selected_files)
        destination = filedialog.asksaveasfilename(title="保存压缩包", initialfile=(Path(source[0]).name + ".zip" if len(source) == 1 else "压缩文件.zip"), defaultextension=".zip", filetypes=[("ZIP 压缩包", "*.zip")], parent=self)
        if destination:
            self.run(compress_file, source, destination, *settings)

    def extract(self):
        settings = self.settings()
        if settings is None:
            return
        source = filedialog.askopenfilename(title="选择压缩包", filetypes=[("ZIP 压缩包", "*.zip"), ("所有文件", "*.*")], parent=self)
        if not source:
            return
        directory = filedialog.askdirectory(title="选择解压输出目录", parent=self)
        if directory:
            self.run(extract_file, source, directory, *settings)

    def run(self, function, *args):
        self.busy = True
        self.compress_button.state(["disabled"])
        self.extract_button.state(["disabled"])
        self.add_button.state(["disabled"])
        self.remove_button.state(["disabled"])
        self.status.set("正在处理，请稍候…")
        def worker():
            try:
                self.events.put((True, function(*args)))
            except Exception as exc:
                self.events.put((False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            success, result = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.compress_button.state(["!disabled"])
            self.extract_button.state(["!disabled"])
            self.add_button.state(["!disabled"])
            self.remove_button.state(["!disabled"])
            self.status.set("完成" if success else "操作失败")
            if success:
                messagebox.showinfo("完成", "已保存到：\n" + result, parent=self)
            else:
                messagebox.showerror("操作失败", "请检查文件头、密码、文件完整性及读写权限。\n\n" + result, parent=self)
        self.after(100, self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo("正在处理", "请等待当前操作完成后再关闭程序。", parent=self)
        else:
            self.destroy()


if __name__ == "__main__":
    App().mainloop()
