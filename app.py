"""本地格式转换助手 1.0 - Windows 本地多媒体格式转换工具。"""
from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_NAME = "本地格式转换助手 1.0"
BG = "#F4F7F6"
PAPER = "#FFFFFF"
DARK = "#143C34"
GREEN = "#08785E"
MINT = "#DFF4EB"
TEXT = "#203D35"
MUTED = "#698078"
WARN = "#C77A13"
ERROR = "#B63B3B"

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm", ".m4v", ".mpeg", ".mpg", ".3gp", ".ts"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma", ".aiff", ".amr"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif", ".ico"}
VIDEO_TARGETS = ["MP4", "MKV", "MOV", "AVI", "WebM", "FLV", "GIF"]
AUDIO_TARGETS = ["MP3", "WAV", "M4A", "AAC", "FLAC", "OGG", "OPUS", "WMA"]
IMAGE_TARGETS = ["JPG", "PNG", "WebP", "BMP", "TIFF", "GIF", "ICO"]
ALL_TARGETS = VIDEO_TARGETS + AUDIO_TARGETS + IMAGE_TARGETS
VIDEO_TARGET_KEYS = {item.lower() for item in VIDEO_TARGETS}
AUDIO_TARGET_KEYS = {item.lower() for item in AUDIO_TARGETS}
IMAGE_TARGET_KEYS = {item.lower() for item in IMAGE_TARGETS}


@dataclass
class ConvertItem:
    source: Path
    category: str
    target: str
    status: str = "等待转换"
    progress: float = 0.0
    output: Optional[Path] = None
    error: str = ""


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / name


def ffmpeg_path() -> Optional[Path]:
    packaged = resource_path("ffmpeg.exe")
    beside_exe = Path(sys.executable).parent / "ffmpeg.exe"
    for item in (packaged, beside_exe):
        if item.exists():
            return item
    found = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    return Path(found) if found else None


def category_for(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in VIDEO_EXTS:
        return "视频"
    if ext in AUDIO_EXTS:
        return "音频"
    if ext in IMAGE_EXTS:
        return "图片"
    return "其他"


def clean_target(target: str) -> str:
    return target.lower().replace("jpeg", "jpg")


def target_fits(category: str, target: str) -> bool:
    value = clean_target(target)
    return ((category == "视频" and value in (VIDEO_TARGET_KEYS | AUDIO_TARGET_KEYS | IMAGE_TARGET_KEYS)) or
            (category == "音频" and value in AUDIO_TARGET_KEYS) or
            (category == "图片" and value in IMAGE_TARGET_KEYS))


def default_target(category: str) -> str:
    return {"视频": "MP4", "音频": "MP3", "图片": "JPG"}[category]


class ConverterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1120x750")
        self.minsize(900, 620)
        self.configure(bg=BG)
        self.items: list[ConvertItem] = []
        self.worker: Optional[threading.Thread] = None
        self.cancel_event = threading.Event()
        self.ui_events: queue.Queue[tuple] = queue.Queue()
        self.output_dir = tk.StringVar(value="与源文件相同目录")
        self.target_var = tk.StringVar(value="MP4")
        self.quality_var = tk.StringVar(value="标准")
        self.size_var = tk.StringVar(value="保持原尺寸")
        self.status_var = tk.StringVar(value="准备就绪：添加文件后即可开始转换")
        self.total_var = tk.StringVar(value="队列中暂无文件")
        self._setup_style()
        self._build_ui()
        self.after(80, self._poll_events)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=PAPER, foreground=TEXT, rowheight=34, fieldbackground=PAPER, font=("Microsoft YaHei UI", 10))
        style.configure("Treeview.Heading", background="#EAF1EE", foreground=DARK, font=("Microsoft YaHei UI", 10, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", MINT)], foreground=[("selected", DARK)])
        style.configure("TCombobox", padding=6, font=("Microsoft YaHei UI", 10))
        style.configure("Horizontal.TProgressbar", troughcolor="#E5ECE8", background=GREEN, thickness=7)

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg=DARK, height=112)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="本地格式转换助手 1.0", bg=DARK, fg="white", font=("Microsoft YaHei UI", 22, "bold")).pack(anchor="w", padx=28, pady=(18, 1))
        tk.Label(header, text="视频 · 音频 · 图片格式转换  ｜  全部在本机完成，不上传文件", bg=DARK, fg="#BCE3D2", font=("Microsoft YaHei UI", 10)).pack(anchor="w", padx=30)
        badge = tk.Label(header, text="  离线处理  ", bg="#286C5A", fg="white", font=("Microsoft YaHei UI", 9, "bold"), padx=7, pady=4)
        badge.place(relx=1.0, x=-28, y=30, anchor="ne")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=18)

        controls = tk.Frame(body, bg=PAPER, highlightbackground="#E0E9E4", highlightthickness=1)
        controls.pack(fill="x", pady=(0, 14))
        controls.grid_columnconfigure(5, weight=1)
        self._button(controls, "＋ 添加文件", self.add_files, GREEN).grid(row=0, column=0, padx=(14, 7), pady=13)
        self._button(controls, "添加文件夹", self.add_folder, "#EAF1EE", fg=GREEN).grid(row=0, column=1, padx=7, pady=13)
        self._button(controls, "清空队列", self.clear_queue, "#F8ECEC", fg=ERROR).grid(row=0, column=2, padx=7, pady=13)
        tk.Label(controls, text="输出格式", bg=PAPER, fg=MUTED, font=("Microsoft YaHei UI", 9, "bold")).grid(row=0, column=3, padx=(22, 4))
        self.target_box = ttk.Combobox(controls, textvariable=self.target_var, values=ALL_TARGETS, state="readonly", width=10)
        self.target_box.grid(row=0, column=4, padx=(0, 12))
        self.target_box.bind("<<ComboboxSelected>>", lambda _e: self._set_target_for_all())
        self._button(controls, "选择输出目录", self.choose_output, "#EAF1EE", fg=GREEN).grid(row=0, column=6, padx=(5, 14), pady=13)

        options = tk.Frame(body, bg=BG)
        options.pack(fill="x", pady=(0, 14))
        self._option_card(options, "转换质量", self.quality_var, ["高清", "标准", "小体积"], 0)
        self._option_card(options, "视频尺寸", self.size_var, ["保持原尺寸", "1080P", "720P", "480P"], 1)
        out = tk.Frame(options, bg="#EAF1EE", padx=14, pady=10)
        out.grid(row=0, column=2, sticky="nsew", padx=(12, 0))
        options.grid_columnconfigure(2, weight=1)
        tk.Label(out, text="输出位置", bg="#EAF1EE", fg=MUTED, font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w")
        tk.Label(out, textvariable=self.output_dir, bg="#EAF1EE", fg=DARK, font=("Microsoft YaHei UI", 10), wraplength=420, justify="left").pack(anchor="w", pady=(3, 0))

        queue_card = tk.Frame(body, bg=PAPER, highlightbackground="#E0E9E4", highlightthickness=1)
        queue_card.pack(fill="both", expand=True)
        top = tk.Frame(queue_card, bg=PAPER)
        top.pack(fill="x", padx=15, pady=(13, 8))
        tk.Label(top, text="转换队列", bg=PAPER, fg=DARK, font=("Microsoft YaHei UI", 14, "bold")).pack(side="left")
        tk.Label(top, textvariable=self.total_var, bg=PAPER, fg=MUTED, font=("Microsoft YaHei UI", 10)).pack(side="left", padx=12)
        self._button(top, "移除选中", self.remove_selected, "#F8ECEC", fg=ERROR, small=True).pack(side="right")

        columns = ("name", "category", "target", "status", "progress")
        self.tree = ttk.Treeview(queue_card, columns=columns, show="headings", selectmode="extended")
        headings = {"name": "文件", "category": "类型", "target": "目标", "status": "状态", "progress": "进度"}
        widths = {"name": 440, "category": 80, "target": 90, "status": 190, "progress": 110}
        for key in columns:
            self.tree.heading(key, text=headings[key])
            self.tree.column(key, width=widths[key], anchor="w" if key == "name" else "center")
        scroll = ttk.Scrollbar(queue_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(14, 0), pady=(0, 13))
        scroll.pack(side="right", fill="y", padx=(0, 10), pady=(0, 13))

        footer = tk.Frame(self, bg="#E7F2ED", height=65)
        footer.pack(fill="x")
        footer.pack_propagate(False)
        tk.Label(footer, textvariable=self.status_var, bg="#E7F2ED", fg="#356759", font=("Microsoft YaHei UI", 10)).pack(side="left", padx=25)
        self.progress = ttk.Progressbar(footer, style="Horizontal.TProgressbar", mode="determinate", maximum=100, length=210)
        self.progress.pack(side="right", padx=(8, 25), pady=23)
        self.start_btn = self._button(footer, "开始转换", self.start_conversion, GREEN, wide=True)
        self.start_btn.pack(side="right", padx=8, pady=12)
        self.cancel_btn = self._button(footer, "停止", self.cancel_conversion, "#F8ECEC", fg=ERROR, small=True)
        self.cancel_btn.pack(side="right", padx=4, pady=12)
        self.cancel_btn.configure(state="disabled")

    def _option_card(self, parent: tk.Widget, title: str, variable: tk.StringVar, values: list[str], column: int) -> None:
        card = tk.Frame(parent, bg=PAPER, highlightbackground="#E0E9E4", highlightthickness=1, padx=13, pady=9)
        card.grid(row=0, column=column, sticky="nsew", padx=(0, 12 if column == 0 else 0))
        tk.Label(card, text=title, bg=PAPER, fg=MUTED, font=("Microsoft YaHei UI", 9, "bold")).pack(anchor="w")
        ttk.Combobox(card, textvariable=variable, values=values, state="readonly", width=14).pack(anchor="w", pady=(4, 0))

    def _button(self, parent: tk.Widget, text: str, command: Callable[[], None], bg: str, fg: str = "white", small: bool = False, wide: bool = False) -> tk.Button:
        btn = tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground=bg, activeforeground=fg,
                        relief="flat", bd=0, cursor="hand2", font=("Microsoft YaHei UI", 9 if small else 10, "bold"),
                        padx=10 if small else (22 if wide else 15), pady=6 if small else 8)
        original = bg
        btn.bind("<ButtonPress-1>", lambda _e: btn.configure(bg="#075C49" if original == GREEN else "#D8E7E0"))
        btn.bind("<ButtonRelease-1>", lambda _e: btn.configure(bg=original))
        return btn

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(title="选择要转换的文件", filetypes=[("支持的媒体文件", "*.mp4 *.mkv *.mov *.avi *.wmv *.flv *.webm *.m4v *.mpeg *.mpg *.3gp *.ts *.mp3 *.wav *.m4a *.aac *.flac *.ogg *.opus *.wma *.aiff *.amr *.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.gif *.ico"), ("所有文件", "*.*")])
        self._append_paths(Path(p) for p in paths)

    def add_folder(self) -> None:
        selected = filedialog.askdirectory(title="选择包含媒体文件的文件夹")
        if not selected:
            return
        files = [p for p in Path(selected).rglob("*") if p.is_file() and category_for(p) != "其他"]
        self._append_paths(files)

    def _append_paths(self, paths) -> None:
        existing = {str(i.source).lower() for i in self.items}
        added = 0
        for path in paths:
            if not path.exists() or category_for(path) == "其他" or str(path).lower() in existing:
                continue
            category = category_for(path)
            chosen = self.target_var.get()
            self.items.append(ConvertItem(path, category, chosen if target_fits(category, chosen) else default_target(category)))
            existing.add(str(path).lower())
            added += 1
        self._refresh_tree()
        self.status_var.set("已添加 %d 个文件，可选择目标格式后开始转换" % added if added else "没有发现可支持的新文件")

    def clear_queue(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.items.clear()
        self._refresh_tree()
        self.status_var.set("队列已清空")

    def remove_selected(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        selected = set(self.tree.selection())
        if not selected:
            return
        self.items = [item for index, item in enumerate(self.items) if str(index) not in selected]
        self._refresh_tree()

    def _set_target_for_all(self) -> None:
        for item in self.items:
            if target_fits(item.category, self.target_var.get()):
                item.target = self.target_var.get()
        self._refresh_tree()

    def choose_output(self) -> None:
        picked = filedialog.askdirectory(title="选择转换后的文件保存位置")
        if picked:
            self.output_dir.set(picked)
            self.status_var.set("输出目录已设置")

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, item in enumerate(self.items):
            progress = "%.0f%%" % item.progress if item.progress else "—"
            self.tree.insert("", "end", iid=str(index), values=(item.source.name, item.category, item.target, item.status, progress))
        total = len(self.items)
        done = sum(1 for i in self.items if i.status == "已完成")
        self.total_var.set("共 %d 个文件%s" % (total, ("，已完成 %d 个" % done) if total else ""))

    def start_conversion(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not self.items:
            messagebox.showinfo(APP_NAME, "请先添加至少一个视频、音频或图片文件。")
            return
        if not ffmpeg_path():
            messagebox.showerror(APP_NAME, "未找到 FFmpeg。请使用完整安装包，或将 ffmpeg.exe 放在程序同目录。")
            return
        self.cancel_event.clear()
        for item in self.items:
            if item.status in ("已完成", "已取消"):
                item.status, item.progress, item.error = "等待转换", 0, ""
        self.start_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.worker = threading.Thread(target=self._convert_all, daemon=True)
        self.worker.start()

    def cancel_conversion(self) -> None:
        self.cancel_event.set()
        self.status_var.set("正在停止当前转换，请稍候…")
        self.cancel_btn.configure(state="disabled")

    def _convert_all(self) -> None:
        count = len(self.items)
        for index, item in enumerate(self.items):
            if self.cancel_event.is_set():
                item.status = "已取消"
                self.ui_events.put(("refresh",))
                continue
            self.ui_events.put(("status", "正在转换 %d / %d：%s" % (index + 1, count, item.source.name)))
            self._convert_one(item, index, count)
        self.ui_events.put(("finished",))

    def _output_for(self, item: ConvertItem) -> Path:
        base = item.source.parent / "转换结果" if self.output_dir.get() == "与源文件相同目录" else Path(self.output_dir.get())
        base.mkdir(parents=True, exist_ok=True)
        ext = clean_target(item.target)
        candidate = base / (item.source.stem + "_已转换." + ext)
        n = 2
        while candidate.exists():
            candidate = base / (item.source.stem + "_已转换_%d." % n + ext)
            n += 1
        return candidate

    def _duration(self, source: Path) -> float:
        ffmpeg = str(ffmpeg_path())
        try:
            result = subprocess.run([ffmpeg, "-hide_banner", "-i", str(source)], capture_output=True, text=True, errors="ignore", timeout=20)
            match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
            if match:
                return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
        except Exception:
            pass
        return 0.0

    def _args_for(self, item: ConvertItem, output: Path) -> list[str]:
        target = clean_target(item.target)
        args = [str(ffmpeg_path()), "-y", "-hide_banner", "-i", str(item.source)]
        quality = self.quality_var.get()
        # 目标格式决定处理方式，因此视频可直接提取为 MP3 / WAV 等音频，
        # 也可截取第一帧保存为常见图片格式。
        if target in AUDIO_TARGET_KEYS and item.category in {"视频", "音频"}:
            return self._audio_args(args, target, quality, output)
        if target in IMAGE_TARGET_KEYS and item.category in {"视频", "图片"}:
            return self._image_args(args, target, quality, output)
        if target in VIDEO_TARGET_KEYS and item.category == "视频":
            if target == "gif":
                return args + ["-vf", "fps=12,scale=720:-1:flags=lanczos", str(output)]
            crf = {"高清": "20", "标准": "24", "小体积": "29"}[quality]
            args += ["-c:v", "libx264", "-crf", crf, "-preset", "medium", "-c:a", "aac", "-b:a", "160k"]
            size = self.size_var.get()
            scales = {"1080P": "scale='min(1920,iw)':-2", "720P": "scale='min(1280,iw)':-2", "480P": "scale='min(854,iw)':-2"}
            if size in scales:
                args += ["-vf", scales[size]]
            if target == "webm":
                args += ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-c:a", "libopus"]
            elif target in {"avi", "flv"}:
                args += ["-c:v", "mpeg4", "-q:v", "5", "-c:a", "libmp3lame"]
        return args + [str(output)]

    @staticmethod
    def _audio_args(args: list[str], target: str, quality: str, output: Path) -> list[str]:
        if target == "mp3":
            args += ["-vn", "-c:a", "libmp3lame", "-b:a", {"高清": "320k", "标准": "192k", "小体积": "128k"}[quality]]
        elif target in {"m4a", "aac"}:
            args += ["-vn", "-c:a", "aac", "-b:a", {"高清": "256k", "标准": "160k", "小体积": "96k"}[quality]]
        elif target == "opus":
            args += ["-vn", "-c:a", "libopus", "-b:a", "128k"]
        elif target == "ogg":
            args += ["-vn", "-c:a", "libvorbis", "-q:a", "5"]
        elif target == "flac":
            args += ["-vn", "-c:a", "flac"]
        elif target == "wav":
            args += ["-vn", "-c:a", "pcm_s16le"]
        else:
            args += ["-vn"]
        return args + [str(output)]

    @staticmethod
    def _image_args(args: list[str], target: str, quality: str, output: Path) -> list[str]:
        args += ["-frames:v", "1", "-update", "1"]
        if target == "jpg":
            args += ["-q:v", {"高清": "2", "标准": "5", "小体积": "10"}[quality]]
        elif target == "webp":
            args += ["-q:v", {"高清": "90", "标准": "75", "小体积": "55"}[quality]]
        return args + [str(output)]

    def _convert_one(self, item: ConvertItem, index: int, count: int) -> None:
        item.status, item.progress = "转换中", 0
        self.ui_events.put(("refresh",))
        output = self._output_for(item)
        target = clean_target(item.target)
        allowed = ((target in VIDEO_TARGET_KEYS and item.category == "视频") or
                   (target in AUDIO_TARGET_KEYS and item.category in {"视频", "音频"}) or
                   (target in IMAGE_TARGET_KEYS and item.category in {"视频", "图片"}))
        if not allowed:
            item.status = "不支持此组合"
            item.error = "请将音频输出用于音频/视频，将图片输出用于图片/视频"
            self.ui_events.put(("refresh",))
            return
        duration = self._duration(item.source)
        try:
            process = subprocess.Popen(self._args_for(item, output), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            while True:
                if self.cancel_event.is_set():
                    process.terminate()
                    item.status = "已取消"
                    break
                line = process.stderr.readline() if process.stderr else ""
                if line:
                    match = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line)
                    if match and duration > 0:
                        elapsed = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
                        item.progress = min(99.0, elapsed / duration * 100)
                        self.ui_events.put(("progress", index, count, item.progress))
                if process.poll() is not None:
                    break
            code = process.wait()
            if code == 0 and output.exists() and not self.cancel_event.is_set():
                item.status, item.progress, item.output = "已完成", 100.0, output
            elif item.status != "已取消":
                item.status = "失败"
                item.error = "编码器不支持或源文件异常"
        except Exception as exc:
            item.status, item.error = "失败", str(exc)
        self.ui_events.put(("refresh",))

    def _poll_events(self) -> None:
        try:
            while True:
                event = self.ui_events.get_nowait()
                if event[0] == "refresh":
                    self._refresh_tree()
                elif event[0] == "status":
                    self.status_var.set(event[1])
                elif event[0] == "progress":
                    _, index, count, partial = event
                    self.progress["value"] = (index + partial / 100) / max(1, count) * 100
                    self._refresh_tree()
                elif event[0] == "finished":
                    done = sum(1 for i in self.items if i.status == "已完成")
                    failed = sum(1 for i in self.items if i.status == "失败")
                    self.progress["value"] = 100 if done else 0
                    self.status_var.set("转换完成：成功 %d 个%s" % (done, ("，失败 %d 个" % failed) if failed else ""))
                    self.start_btn.configure(state="normal")
                    self.cancel_btn.configure(state="disabled")
                    self._refresh_tree()
        except queue.Empty:
            pass
        self.after(80, self._poll_events)


if __name__ == "__main__":
    ConverterApp().mainloop()
