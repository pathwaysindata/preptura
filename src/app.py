"""Preptura – Tabular Data Pre‑processor
Core GUI application (Tkinter)
Only change in this revision: add a menubar with a gear‑icon Settings entry.
Future steps will wire the Settings window; for now it shows a placeholder dialog.
"""

from __future__ import annotations

import os
import string
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd

# ---------------------------------------------------------------------------
# Local utilities (already exist in your repo)
# ---------------------------------------------------------------------------
from utils.config import load_config, save_config
from utils.file_manager import list_supported_files


class PrepturaApp:
    """Main application window for Preptura."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Preptura: Tabular Data Preprocessor")
        self._create_menubar()  # NEW
        self._build_ui()

        # Application state --------------------------------------------------
        self.current_folder: Path | None = None

    # ---------------------------------------------------------------------
    # Menubar (NEW)
    # ---------------------------------------------------------------------
    def _create_menubar(self) -> None:
        """Create a basic menubar with File & ⚙ Settings cascades."""
        menubar = tk.Menu(self.root)

        # File ----------------------------------------------------------------
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Select Folder…", command=self.select_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Settings ------------------------------------------------------------
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Open Settings", command=self.open_config_window)
        # Gear glyph in cascade label (renders on most modern fonts)
        menubar.add_cascade(label="⚙ Settings", menu=settings_menu)

        self.root.config(menu=menubar)

    # ---------------------------------------------------------------------
    # UI construction (existing, unchanged except for folder button callback)
    # ---------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Assemble the two‑pane file‑manager UI (simplified)."""

        # Paned window gives a resizable splitter between tree & file list
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # Left: directory tree -------------------------------------------------
        self.dir_tree = ttk.Treeview(paned)
        self.dir_tree.heading("#0", text="Folders", anchor="w")
        self._populate_drives()  # load root nodes
        self.dir_tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.dir_tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        paned.add(self.dir_tree, weight=1)

        # Right: file list -----------------------------------------------------
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)

        self.file_listbox = tk.Listbox(right_frame, height=15)
        self.file_listbox.pack(fill="both", expand=True, padx=6, pady=6)

        # Buttons row (existing stubs) ---------------------------------------
        button_row = ttk.Frame(right_frame)
        button_row.pack(pady=(0, 6))
        ttk.Button(button_row, text="Run Diagnostics", command=self.run_diagnostics, state="disabled").pack(side="left", padx=4)
        ttk.Button(button_row, text="Save Cleaned File", command=self.save_cleaned_file, state="disabled").pack(side="left", padx=4)

    # ------------------------------------------------------------------
    # Directory‑tree helpers
    # ------------------------------------------------------------------
    def _populate_drives(self) -> None:
        """Populate top‑level drive / root nodes (cross‑platform)."""
        if os.name == "nt":  # Windows
            for drive_letter in string.ascii_uppercase:
                drive = f"{drive_letter}:\\"
                if os.path.exists(drive):
                    node = self.dir_tree.insert("", "end", text=drive, values=[drive])
                    self.dir_tree.insert(node, "end")  # dummy child
        else:  # *nix – start from root
            node = self.dir_tree.insert("", "end", text="/", values=["/"])
            self.dir_tree.insert(node, "end")

    def _on_tree_open(self, event):
        node = self.dir_tree.focus()
        path = Path(self._get_full_path(node))
        # Clear dummy children
        self.dir_tree.delete(*self.dir_tree.get_children(node))
        for child in sorted(path.iterdir()):
            if child.is_dir():
                child_node = self.dir_tree.insert(node, "end", text=child.name, values=[str(child)])
                # Add dummy child if directory has sub‑dirs
                if any(p.is_dir() for p in path.iterdir()):
                    self.dir_tree.insert(child_node, "end")

    def _on_tree_select(self, event):
        node = self.dir_tree.focus()
        path_str = self._get_full_path(node)
        self.current_folder = Path(path_str)
        self._refresh_file_list()

    def _get_full_path(self, node_id: str) -> str:
        components = []
        while node_id:
            components.insert(0, self.dir_tree.item(node_id, "text"))
            node_id = self.dir_tree.parent(node_id)
        return os.path.join(*components)

    # ------------------------------------------------------------------
    # File‑list refresh
    # ------------------------------------------------------------------
    def _refresh_file_list(self) -> None:
        self.file_listbox.delete(0, tk.END)
        if not self.current_folder:
            return
        for file_path in list_supported_files(self.current_folder):
            self.file_listbox.insert(tk.END, file_path.name)

    # ------------------------------------------------------------------
    # Menu callbacks / placeholders
    # ------------------------------------------------------------------
    def select_folder(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.current_folder = Path(folder)
            self._refresh_file_list()

    def open_config_window(self) -> None:
        messagebox.showinfo("Settings", "Settings window coming soon!")

    # ------------------------------------------------------------------
    # Existing stubs (no change)
    # ------------------------------------------------------------------
    def run_diagnostics(self):
        pass  # to be implemented

    def save_cleaned_file(self):
        pass  # to be implemented


# ---------------------------------------------------------------------------
# Launch application --------------------------------------------------------
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = PrepturaApp(root)
    root.geometry("900x600")
    root.mainloop()
