from tkinter import Toplevel, BooleanVar, Checkbutton, Button, Label, Frame

class DiagnosticsConfigWindow:
    def __init__(self, master, settings_callback, current_config=None):
        self.master = master
        self.settings_callback = settings_callback
        self.config_window = Toplevel(master)
        self.config_window.title("Diagnostics Options")
        self.config_window.geometry("300x250")

        self.config_options = {
            "empty_columns": BooleanVar(value=True),
            "empty_rows": BooleanVar(value=True),
            "missing_headers": BooleanVar(value=True),
            "mixed_types": BooleanVar(value=True)
        }

        if current_config:
            for key in self.config_options:
                self.config_options[key].set(current_config.get(key, True))

        self.build_ui()

    def build_ui(self):
        frame = Frame(self.config_window, padx=10, pady=10)
        frame.pack(expand=True, fill='both')

        Label(frame, text="Select diagnostics to run:").pack(anchor='w')

        for key, var in self.config_options.items():
            Checkbutton(frame, text=key.replace("_", " ").title(), variable=var).pack(anchor='w')

        btn_frame = Frame(frame)
        btn_frame.pack(pady=10)

        Button(btn_frame, text="Select All", command=self.select_all).grid(row=0, column=0, padx=5)
        Button(btn_frame, text="Deselect All", command=self.deselect_all).grid(row=0, column=1, padx=5)

        Button(frame, text="Save Settings", command=self.save_settings).pack(pady=10)

    def select_all(self):
        for var in self.config_options.values():
            var.set(True)

    def deselect_all(self):
        for var in self.config_options.values():
            var.set(False)

    def save_settings(self):
        config = {key: var.get() for key, var in self.config_options.items()}
        self.settings_callback(config)
        self.config_window.destroy()