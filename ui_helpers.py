import tkinter as tk
from tkinter import ttk


class ScrollableFrame(ttk.Frame):
    def __init__(self, master, canvas_bg="#e8e7df", **kwargs):
        ttk.Frame.__init__(self, master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, background=canvas_bg, borderwidth=0,
                                highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.content = ttk.Frame(self.canvas)
        self.content_window = self.canvas.create_window(
            (0, 0), window=self.content, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.content.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_content)

    def _resize_content(self, event):
        self.canvas.itemconfigure(self.content_window, width=event.width)
        self._update_scroll_region()

    def _update_scroll_region(self, event=None):
        bounds = self.canvas.bbox("all")
        if bounds is None:
            return
        self.canvas.configure(scrollregion=bounds)
        needs_scrollbar = self.content.winfo_reqheight() > self.canvas.winfo_height()
        if needs_scrollbar and not self.scrollbar.winfo_manager():
            self.scrollbar.grid(row=0, column=1, sticky="ns")
        elif not needs_scrollbar and self.scrollbar.winfo_manager():
            self.scrollbar.grid_remove()