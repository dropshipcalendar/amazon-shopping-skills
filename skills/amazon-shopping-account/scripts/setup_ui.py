"""Minimal local credential window. No network, provider actions, or telemetry."""
from pathlib import Path

from workflow import WorkflowError


BLUE = "#0077f9"
INK = "#151e3a"
FIELD = "#fbfcff"
LINE = "#dce3ee"


def credential_values(fields):
    """Only explicitly entered fields are updated; empty fields are preserved."""
    return {name: field.get() for name, field in fields.items() if field.get()}


def save_credentials(account, fields, saver):
    values = credential_values(fields)
    try:
        return saver(account, {}, values, replace_credentials=True)
    finally:
        values.clear()


def show_setup(account, save_settings):
    try:
        import tkinter as tk
        from tkinter import font, messagebox
        window = tk.Tk()
    except Exception:
        raise WorkflowError("Local setup window unavailable; run setup.py configure ACCOUNT_ID --prompt in your own terminal") from None
    window.title("Dropship Calendar — API credentials")
    window.configure(bg="#eaf7ff")
    window.geometry("480x555")
    window.minsize(440, 540)
    available = set(font.families(window))
    family = next((name for name in ("Plus Jakarta Sans", "Segoe UI", "Avenir Next", "DejaVu Sans") if name in available), "TkDefaultFont")
    canvas = tk.Canvas(window, bg="white", highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True, padx=10, pady=10)

    body = tk.Frame(canvas, bg="white")
    body.pack(fill="both", expand=True, padx=30, pady=30)
    corner = tk.Canvas(body, width=85, height=55, bg="white", highlightthickness=0, bd=0)
    corner.place(relx=1, x=0, y=0, anchor="ne")
    corner.create_oval(20, -85, 180, 65, fill="#eaf7ff", outline="")
    corner.create_oval(0, -45, 50, 5, fill="#eafff4", outline="")
    brand = tk.Frame(body, bg="white")
    brand.pack(anchor="w")
    logo_path = Path(__file__).resolve().parents[1] / "assets/dropship-calendar.png"
    try:
        window.brand_image = tk.PhotoImage(file=str(logo_path)).subsample(2, 2)
        tk.Label(brand, image=window.brand_image, bg="white", bd=0).pack(side="left", padx=(0, 9))
    except tk.TclError:
        # A missing/corrupt asset must not prevent private credential entry.
        pass
    tk.Label(brand, text="Dropship", bg="white", fg=INK, font=(family, 11, "bold")).pack(side="left")
    tk.Label(brand, text="Calendar", bg="white", fg=BLUE, font=(family, 11, "bold")).pack(side="left", padx=(3, 0))
    tk.Label(body, text="API credentials", bg="white", fg=INK, font=(family, 20, "bold")).pack(anchor="w", pady=(22, 25))

    def rounded(parent, fill, stroke, height):
        control = tk.Canvas(parent, height=height, bg="white", highlightthickness=0, bd=0)
        def draw(event):
            control.delete("shape")
            w, h, r = event.width - 1, event.height - 1, 11
            points = (r, 1, w-r, 1, w, 1, w, r, w, h-r, w, h, w-r, h, r, h, 1, h, 1, h-r, 1, r, 1, 1)
            control.create_polygon(points, smooth=True, splinesteps=20, fill=fill, outline=stroke, tags="shape")
            control.tag_lower("shape")
            if hasattr(control, "embedded"):
                control.coords(control.embedded, event.width / 2, event.height / 2)
                control.itemconfigure(control.embedded, width=max(1, event.width - 26), height=event.height - 12)
        control.bind("<Configure>", draw)
        return control

    fields = {}
    for name, label, masked in (("AGENTMAIL_API_KEY", "AgentMail API key", True),
                                ("TEXTVERIFIED_API_KEY", "TextVerified API key", True),
                                ("TEXTVERIFIED_API_USERNAME", "TextVerified username", False)):
        tk.Label(body, text=label, bg="white", fg=INK, font=(family, 10)).pack(anchor="w", pady=(0, 7))
        surround = rounded(body, FIELD, LINE, 47)
        surround.pack(fill="x", pady=(0, 19))
        entry = tk.Entry(surround, bg=FIELD, fg=INK, insertbackground=BLUE, relief="flat", bd=0,
                         highlightthickness=0, font=(family, 11), show="*" if masked else "")
        surround.embedded = surround.create_window(0, 0, window=entry)
        entry.bind("<FocusIn>", lambda event, box=surround: box.itemconfigure("shape", outline=BLUE))
        entry.bind("<FocusOut>", lambda event, box=surround: box.itemconfigure("shape", outline=LINE))
        fields[name] = entry

    actions = tk.Frame(body, bg="white")
    actions.pack(fill="x", pady=(5, 0))
    actions.columnconfigure(0, weight=1)
    save_bg = rounded(actions, BLUE, BLUE, 46)
    save_bg.grid(row=0, column=0, sticky="ew", padx=(0, 12))

    def save():
        try:
            # Save applies only to visible credential fields; it never approves
            # an SMS budget or changes account/marketplace settings implicitly.
            save_credentials(account, fields, save_settings)
            for field in fields.values():
                field.delete(0, "end")
            save_button.configure(text="Saved", state="disabled")
            window.after(700, window.destroy)
        except WorkflowError as exc:
            messagebox.showerror("Could not save", str(exc), parent=window)
        except Exception:
            messagebox.showerror("Could not save", "Check native credential storage and try again. No credentials were logged.", parent=window)

    save_button = tk.Button(save_bg, text="Save", command=save, bg=BLUE, fg="white", activebackground="#006ce3",
                            activeforeground="white", relief="flat", bd=0, highlightthickness=0, font=(family, 11, "bold"), takefocus=True)
    save_bg.embedded = save_bg.create_window(0, 0, window=save_button)
    tk.Button(actions, text="Configure later", command=window.destroy, bg="white", fg="#66718a",
              activebackground="#f5f8fc", activeforeground=INK, relief="flat", bd=0,
              highlightthickness=0, padx=8, font=(family, 10), takefocus=True).grid(row=0, column=1, sticky="ns")
    fields["AGENTMAIL_API_KEY"].focus_set()
    window.mainloop()
