import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import os

class PrepturaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Preptura: Tabular Data Preprocessor")
        self.df = None
        self.file_path = ""

        self.build_ui()

    def build_ui(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Button(frame, text="Open CSV", command=self.load_file).grid(row=0, column=0, padx=5, pady=5)
        self.diagnose_btn = ttk.Button(frame, text="Run Diagnostics", command=self.run_diagnostics, state='disabled')
        self.diagnose_btn.grid(row=0, column=1, padx=5, pady=5)
        self.save_btn = ttk.Button(frame, text="Save Cleaned File", command=self.save_file, state='disabled')
        self.save_btn.grid(row=0, column=2, padx=5, pady=5)

        self.log_output = tk.Text(frame, height=20, width=100, wrap="word")
        self.log_output.grid(row=1, column=0, columnspan=3, pady=10)

    def load_file(self):
        self.file_path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not self.file_path:
            return
        try:
            self.df = pd.read_csv(self.file_path)
            self.log(f"Loaded: {os.path.basename(self.file_path)} with {self.df.shape[0]} rows and {self.df.shape[1]} columns.")
            self.diagnose_btn.config(state='normal')
            self.save_btn.config(state='normal')
        except Exception as e:
            messagebox.showerror("Error", f"Unable to read file:\n{e}")

    def run_diagnostics(self):
        if self.df is None:
            return

        self.log_output.delete("1.0", tk.END)

        self.log("=== Data Diagnostics ===")
        self.log(f"Shape: {self.df.shape}")
        self.log(f"Columns: {list(self.df.columns)}")

        empty_cols = [col for col in self.df.columns if self.df[col].isnull().all()]
        self.log(f"Empty columns: {empty_cols or 'None'}")

        empty_rows = self.df[self.df.isnull().all(axis=1)]
        self.log(f"Empty rows: {len(empty_rows)}")

        type_issues = {}
        for col in self.df.columns:
            if self.df[col].map(type).nunique() > 1:
                type_issues[col] = self.df[col].map(type).value_counts().to_dict()
        self.log(f"Mixed-type columns: {type_issues or 'None'}")

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

    def log(self, message):
        self.log_output.insert(tk.END, str(message) + "\n")
        self.log_output.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = PrepturaApp(root)
    root.mainloop()
