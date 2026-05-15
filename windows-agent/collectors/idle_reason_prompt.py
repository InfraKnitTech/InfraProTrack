from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IdleReason:
    category: str | None = None
    reason: str | None = None


class IdleReasonPrompt:
    def __init__(self, categories: list[str] | None = None):
        self.categories = categories or [
            "Lunch / meal break",
            "Meeting",
            "Phone call",
            "Personal break",
            "System issue",
            "Other",
        ]

    def ask(self, idle_duration_seconds: int) -> IdleReason:
        try:
            import tkinter as tk
            from tkinter import messagebox, ttk
        except Exception:
            return IdleReason()

        result = IdleReason()
        submitted = False
        try:
            root = tk.Tk()
            root.title("InfraProTrack Idle Reason")
            root.attributes("-topmost", True)
            root.resizable(False, False)
        except Exception:
            return result

        duration_minutes = max(1, round(idle_duration_seconds / 60))
        container = ttk.Frame(root, padding=18)
        container.grid(row=0, column=0, sticky="nsew")

        ttk.Label(
            container,
            text=f"You were idle for about {duration_minutes} minute(s).",
            font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(container, text="Select a reason or enter your own note.").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )

        selected = tk.StringVar(value=self.categories[0] if self.categories else "Other")
        ttk.Label(container, text="Category").grid(row=2, column=0, sticky="w")
        category_box = ttk.Combobox(container, textvariable=selected, values=self.categories, state="readonly", width=34)
        category_box.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 10))

        ttk.Label(container, text="Manual reason").grid(row=4, column=0, sticky="w")
        note = tk.Text(container, width=42, height=4)
        note.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(4, 12))

        def submit() -> None:
            nonlocal submitted
            result.category = selected.get().strip() or None
            typed = note.get("1.0", "end").strip()
            result.reason = typed or result.category
            submitted = True
            root.destroy()

        def block_close() -> None:
            messagebox.showwarning(
                "Idle reason required",
                "Please submit an idle reason before closing this prompt.",
                parent=root,
            )
            root.lift()
            root.focus_force()

        button = ttk.Button(container, text="Submit", command=submit)
        button.grid(row=6, column=1, sticky="e")
        root.bind("<Return>", lambda _event: submit())
        root.bind("<Escape>", lambda _event: block_close())
        root.protocol("WM_DELETE_WINDOW", block_close)
        try:
            root.grab_set()
        except Exception:
            pass
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f"+{x}+{y}")
        root.focus_force()
        root.mainloop()
        if not submitted:
            return IdleReason()
        return result
