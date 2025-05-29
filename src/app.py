import os
import string
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd

from diagnostics_config import DiagnosticsConfigWindow
from utils.config import load_config, save_config
from utils.file_manager import list_supported_files


class PrepturaApp:
    """Main application window for Preptura."""

    def __init__(self, root):
        self.root = root
        self.root.title("Preptura: Tabular Data Preprocessor")
        self.root.minsize(900, 600)

        # --------------------------------------------------------------------------------------
        # Runtime‑state attributes
        # --------------------------------------------------------------------------------------
        self.df = None  # Currently loaded DataFrame
        self.selected_file = None  # pathlib.Path object for current file
        self.current_folder = None  # Folder displayed in the *file* pane
        self.files = []  # pathlib.Path collection for files in current folder

        # Diagnostics configuration (will eventually move to its own module/UI)
        self.diagnostics_config = {
            "empty_columns": True,
            "empty_rows": True,
            "missing_headers": True,
            "mixed_types": True,
        }

        # --------------------------------------------------------------------------------------
        # Config persistence – load once on start‑up
        # --------------------------------------------------------------------------------------
        self.config = load_config()
        self.default_folder = self.config.get("default_folder")

        # --------------------------------------------------------------------------------------
        # Build the UI *first* so we have widgets to manipulate later
        # --------------------------------------------------------------------------------------
        self._build_ui()

        # Populate the directory tree and, if a default folder is configured, pre‑select it
        self._populate_roots()
        if self.default_folder and Path(self.default_folder).exists():
            self._select_path_in_tree(Path(self.default_folder))
        else:
            # Immediately focus on the tree so users can navigate with keyboard‑arrows
            self.dir_tree.focus_set()

    # ==================================================================================================
    # UI construction helpers
    # ==================================================================================================
    def _build_ui(self):
        """Create and lay out all widgets."""

        # Configure root grid so the PanedWindow fills the window
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        # Split main window into *navigator* (left) and *work* (right) with a PanedWindow
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.grid(row=0, column=0, sticky="nsew")

        # ----------------------------------------------------------------------------------
        # 1️⃣  Directory‑tree pane (left)
        # ----------------------------------------------------------------------------------
        nav_frame = ttk.Frame(paned)
        nav_frame.rowconfigure(0, weight=1)
        nav_frame.columnconfigure(0, weight=1)

        self.dir_tree = ttk.Treeview(
            nav_frame,
            columns=("fullpath",),  # hidden column that stores the absolute path
            displaycolumns=(),  # hide it from the UI
            show="tree",
        )
        self.dir_tree.grid(row=0, column=0, sticky="nsew")

        # Scrollbar for directory tree
        nav_scroll = ttk.Scrollbar(nav_frame, orient="vertical", command=self.dir_tree.yview)
        nav_scroll.grid(row=0, column=1, sticky="ns")
        self.dir_tree.configure(yscrollcommand=nav_scroll.set)

        # Bindings for lazy‑loading and selection handling
        self.dir_tree.bind("<<TreeviewOpen>>", self._on_tree_expand)
        self.dir_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        paned.add(nav_frame, weight=1)  # give navigator ~25 % width

        # ----------------------------------------------------------------------------------
        # 2️⃣  Work pane (right) – file list, actions & log
        # ----------------------------------------------------------------------------------
        work_frame = ttk.Frame(paned, padding=10)
        work_frame.rowconfigure(2, weight=1)  # log Text grows vertically
        work_frame.columnconfigure(0, weight=1)
        paned.add(work_frame, weight=3)

        # Top‑row: optional *Select default folder* button (de‑emphasised but still available)
        select_btn = ttk.Button(work_frame, text="📂 Set Default Folder", command=self._choose_default_folder)
        select_btn.grid(row=0, column=0, sticky="w", pady=(0, 8))

        # File list
        self.file_listbox = tk.Listbox(work_frame, height=10)
        self.file_listbox.grid(row=1, column=0, sticky="nsew")
        self.file_listbox.bind("<<ListboxSelect>>", self._on_file_select)

        # Action buttons (Diagnostics / Save cleaned)
        btn_row = ttk.Frame(work_frame)
        btn_row.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        btn_row.columnconfigure((0, 1, 2), weight=1)

        self.run_btn = ttk.Button(btn_row, text="Run Diagnostics", command=self._run_diagnostics, state="disabled")
        self.run_btn.grid(row=0, column=0, padx=2)

        self.save_btn = ttk.Button(btn_row, text="Save Cleaned File", command=self._save_file, state="disabled")
        self.save_btn.grid(row=0, column=1, padx=2)

        opts_btn = ttk.Button(btn_row, text="Options", command=self._open_config_window)
        opts_btn.grid(row=0, column=2, padx=2)

        # Log output (read‑only Text)
        self.log_output = tk.Text(work_frame, wrap="word", state="disabled")
        self.log_output.grid(row=3, column=0, sticky="nsew", pady=(8, 0))

    # ==================================================================================================
    # Directory‑tree helpers
    # ==================================================================================================
    def _populate_roots(self):
        """Insert platform-specific *root* entries into the directory tree."""
        if os.name == "nt":  # Windows ⇒ drives A: … Z:
            for letter in string.ascii_uppercase:
                drive = Path(f"{letter}:\\")
                if drive.exists():
                    node = self.dir_tree.insert("", "end", text=str(drive), values=(str(drive),))
                    self.dir_tree.insert(node, "end")  # dummy child for lazy expansion
        else:  # Unix‑likes – show filesystem root and common mount points
            for base in {Path("/"), Path.home(), Path("/mnt"), Path("/media")}:
                if base.exists():
                    node = self.dir_tree.insert("", "end", text=str(base), values=(str(base),))
                    self.dir_tree.insert(node, "end")

    def _on_tree_expand(self, event):
        """Populate a node with its sub‑directories when the node is expanded."""
        node = self.dir_tree.focus()
        path = Path(self.dir_tree.set(node, "fullpath"))

        # If already populated (no dummy child), do nothing
        if len(self.dir_tree.get_children(node)) and self.dir_tree.item(self.dir_tree.get_children(node)[0], "values"):
            return

        # Clear any existing (dummy) children
        for child in self.dir_tree.get_children(node):
            self.dir_tree.delete(child)

        # Add sub‑directories (ignore permission errors)
        try:
            for p in sorted([d for d in path.iterdir() if d.is_dir() and not d.name.startswith(".")]):
                child_node = self.dir_tree.insert(node, "end", text=p.name, values=(str(p),))
                # Insert a dummy so the node gets a twisty arrow – will be replaced on further expand
                if any(sub.is_dir() for sub in p.iterdir()):
                    self.dir_tree.insert(child_node, "end")
        except PermissionError:
            pass  # Non‑fatal – just skip folders we cannot access

    def _on_tree_select(self, event):
        """Update the *file* pane when user selects a folder in the tree."""
        node = self.dir_tree.focus()
        if not node:
            return
        path = Path(self.dir_tree.set(node, "fullpath"))
        self._refresh_file_list(path)

    def _select_path_in_tree(self, target: Path):
        """Expand parent nodes & select *target* if it exists in the tree (used for default folder)."""
        parts = target.resolve().parts
        current_nodes = self.dir_tree.get_children("")
        node_path_dict = {self.dir_tree.set(n, "fullpath"): n for n in current_nodes}

        accum_path = Path(parts[0])
        node = node_path_dict.get(str(accum_path))
        if not node:
            return  # Could not map path back to tree (unlikely but safe‑guard)
        self.dir_tree.item(node, open=True)
        self._on_tree_expand(None)  # Populate first level
        for part in parts[1:]:
            accum_path /= part
            for child in self.dir_tree.get_children(node):
                if Path(self.dir_tree.set(child, "fullpath")) == accum_path:
                    node = child
                    self.dir_tree.item(node, open=True)
                    self._on_tree_expand(None)
                    break
        self.dir_tree.selection_set(node)
        self.dir_tree.focus(node)
        self._refresh_file_list(target)

    # ==================================================================================================
    # File‑pane helpers
    # ==================================================================================================
    def _refresh_file_list(self, folder: Path):
        """Populate *file_listbox* with CSV (supported) files from *folder*."""
        if not folder.exists():
            return
        self.current_folder = folder
        self.files = list_supported_files(str(folder))

        self.file_listbox.delete(0, tk.END)
        for f in self.files:
            self.file_listbox.insert(tk.END, f.name)
        self._log(f"Folder: {folder} – displaying {len(self.files)} CSV files")

        # Disable buttons when changing folder
        self.df = None
        self.selected_file = None
        self.run_btn.config(state="disabled")
        self.save_btn.config(state="disabled")

    # ==================================================================================================
    # Button‑callbacks & Diagnostics
    # ==================================================================================================
    def _choose_default_folder(self):
        folder = filedialog.askdirectory(title="Select default folder")
        if not folder:
            return
        self.default_folder = folder
        self.config["default_folder"] = folder
        save_config(self.config)
        self._select_path_in_tree(Path(folder))

    def _on_file_select(self, event):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        self.selected_file = self.files[sel[0]]
        try:
            self.df = pd.read_csv(self.selected_file)
            self._log(f"Loaded: {self.selected_file.name} – {self.df.shape[0]} rows × {self.df.shape[1]} columns")
            self.run_btn.config(state="normal")
            self.save_btn.config(state="normal")
        except Exception as exc:
            messagebox.showerror("Error", f"Could not load file:\n{exc}")
            self.df = None
            self.run_btn.config(state="disabled")
            self.save_btn.config(state="disabled")

    def _run_diagnostics(self):
        if self.df is None:
            return
        self._clear_log()
        self._log("=== Data Diagnostics ===")
        self._log(f"Shape: {self.df.shape}")
        self._log(f"Columns: {list(self.df.columns)}")

        if self.diagnostics_config.get("empty_columns"):
            empties = [c for c in self.df.columns if self.df[c].isnull().all()]
            self._log(f"Empty columns: {empties or 'None'}")

        if self.diagnostics_config.get("empty_rows"):
            empty_rows = self.df[self.df.isnull().all(axis=1)]
            self._log(f"Empty rows: {len(empty_rows)}")

        if self.diagnostics_config.get("mixed_types"):
            issues = {}
            for col in self.df.columns:
                if self.df[col].map(type).nunique() > 1:
                    issues[col] = self.df[col].map(type).value_counts().to_dict()
            self._log(f"Mixed‑type columns: {issues or 'None'}")

        if self.diagnostics_config.get("missing_headers"):
            if any(str(c).startswith("Unnamed") for c in self.df.columns):
                self._log("Potential missing headers detected.")
            else:
                self._log("Headers appear present.")

    def _save_file(self):
        if self.df is None:
            return
        cleaned = self.df.dropna(how="all").dropna(axis=1, how="all")
        save_path = filedialog.asksaveasfilename(
            title="Save cleaned CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialdir=str(self.current_folder) if self.current_folder else "~",
        )
        if not save_path:
            return
        try:
            cleaned.to_csv(save_path, index=False)
            self._log(f"Saved cleaned file to: {save_path}")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to save file:\n{exc}")

    def _open_config_window(self):
        DiagnosticsConfigWindow(self.root, self._apply_diagnostics_config, self.diagnostics_config)

    def _apply_diagnostics_config(self, config):
        self.diagnostics_config = config
        self._log(f"Updated diagnostics settings: {config}")

    # ==================================================================================================
    # Logging helpers – keep Text read‑only for better UX
    # ==================================================================================================
    def _log(self, msg: str):
        self.log_output.configure(state="normal")
        self.log_output.insert(tk.END, msg + "\n")
        self.log_output.configure(state="disabled")
        self.log_output.see(tk.END)

    def _clear_log(self):
        self.log_output.configure(state="normal")
        self.log_output.delete("1.0", tk.END)
        self.log_output.configure(state="disabled")


# =====================================================================================================
#  Entry‑point helper – keep separate so imports don’t execute Tk when used as a module
# =====================================================================================================

def main():
    root = tk.Tk()
    PrepturaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
