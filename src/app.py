"""
Updated app.py to:
- Use config to load saved folder or prompt user on startup
- Prompt user for folder if not set or invalid
- Offer option to save folder as default in config
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import os
from pathlib import Path

from diagnostics_config import DiagnosticsConfigWindow
from utils.config import load_config, save_config
from utils.file_manager import list_supported_files

class PrepturaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Preptura: Tabular Data Preprocessor")
        self.df = None
        self.config = load_config()
        self.selected_folder = self.config.get("default_folder", "")
        self.diagnostics_config = {
            "empty_columns": True,
            "empty_rows": True,
            "missing_headers": True,
            "mixed_types": True
        }

        self.files = []
        self.selected_file = None

        self.build_ui()
        self.load_or_prompt_folder()

    def build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.grid(row=0, column=0, sticky="nsew")

        ttk.Button(top, text="Select Folder", command=self.select_folder).grid(row=0, column=0, padx=5, pady=5)
        self.folder_label = ttk.Label(top, text="No folder selected")
        self.folder_label.grid(row=0, column=1, columnspan=3, sticky="w")

        self.file_listbox = tk.Listbox(top, width=60)
        self.file_listbox.grid(row=1, column=0, columnspan=4, pady=5)
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_select)

        self.diagnose_btn = ttk.Button(top, text="Run Diagnostics", command=self.run_diagnostics, state='disabled')
        self.diagnose_btn.grid(row=2, column=0, padx=5, pady=5)

        self.save_btn = ttk.Button(top, text="Save Cleaned File", command=self.save_file, state='disabled')
        self.save_btn.grid(row=2, column=1, padx=5, pady=5)

        ttk.Button(top, text="Options", command=self.open_config_window).grid(row=2, column=2, padx=5, pady=5)

        self.log_output = tk.Text(top, height=20, width=100, wrap="word")
        self.log_output.grid(row=3, column=0, columnspan=4, pady=10)

    def load_or_prompt_folder(self):
        if not self.selected_folder or not Path(self.selected_folder).exists():
            folder = filedialog.askdirectory(title="Select folder to scan")
            if not folder:
                messagebox.showinfo("No folder", "Application requires a folder to proceed.")
                self.root.quit()
                return
            self.selected_folder = folder
            self.ask_store_folder(folder)
        self.refresh_file_list()

    def ask_store_folder(self, folder):
        if messagebox.askyesno("Save Folder", "Would you like to save this folder as default?"):
            self.config["default_folder"] = folder
            save_config(self.config)

    def select_folder(self):
        folder = filedialog.askdirectory(title="Select folder")
        if folder:
            self.selected_folder = folder
            self.config["default_folder"] = folder
            save_config(self.config)
            self.refresh_file_list()

    def refresh_file_list(self):
        self.files = list_supported_files(self.selected_folder)
        self.folder_label.config(text=f"Folder: {self.selected_folder}")
        self.file_listbox.delete(0, tk.END)
        for f in self.files:
            self.file_listbox.insert(tk.END, f.name)

    def on_file_select(self, event):
        selection = self.file_listbox.curselection()
        if not selection:
            self.df = None
            self.selected_file = None
            self.diagnose_btn.config(state='disabled')
            self.save_btn.config(state='disabled')
            return

        index = selection[0]
        self.selected_file = self.files[index]
        try:
            self.df = pd.read_csv(self.selected_file)
            self.log(f"Loaded: {self.selected_file.name} with {self.df.shape[0]} rows and {self.df.shape[1]} columns.")
            self.diagnose_btn.config(state='normal')
            self.save_btn.config(state='normal')
        except Exception as e:
            self.df = None
            messagebox.showerror("Error", f"Could not load file:\n{e}")

    def run_diagnostics(self):
        if self.df is None:
            return

        self.log_output.delete("1.0", tk.END)
        self.log("=== Data Diagnostics ===")
        self.log(f"Shape: {self.df.shape}")
        self.log(f"Columns: {list(self.df.columns)}")

        if self.diagnostics_config.get("empty_columns"):
            empty_cols = [col for col in self.df.columns if self.df[col].isnull().all()]
            self.log(f"Empty columns: {empty_cols or 'None'}")

        if self.diagnostics_config.get("empty_rows"):
            empty_rows = self.df[self.df.isnull().all(axis=1)]
            self.log(f"Empty rows: {len(empty_rows)}")

        if self.diagnostics_config.get("mixed_types"):
            type_issues = {}
            for col in self.df.columns:
                if self.df[col].map(type).nunique() > 1:
                    type_issues[col] = self.df[col].map(type).value_counts().to_dict()
            self.log(f"Mixed-type columns: {type_issues or 'None'}")

        if self.diagnostics_config.get("missing_headers"):
            if any(str(col).startswith("Unnamed") for col in self.df.columns):
                self.log("Potential missing headers detected.")
            else:
                self.log("Headers appear present.")

    def save_file(self):
        if self.df is None:
            return
        cleaned = self.df.dropna(how="all").dropna(axis=1, how="all")
        save_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not save_path:
            return
        try:
            cleaned.to_csv(save_path, index=False)
            self.log(f"Saved cleaned file to: {save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file:\n{e}")

    def open_config_window(self):
        DiagnosticsConfigWindow(self.root, self.apply_config, self.diagnostics_config)

    def apply_config(self, config):
        self.diagnostics_config = config
        self.log(f"Updated diagnostics settings: {config}")

    def log(self, message):
        self.log_output.insert(tk.END, str(message) + "\n")
        self.log_output.see(tk.END)
