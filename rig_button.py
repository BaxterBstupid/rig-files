#!/usr/bin/env python3
import tkinter as tk, subprocess, os
root = tk.Tk()
root.title("RIG")
root.geometry("420x420+40+40")        # size WxH + position x+y  (change freely)
root.attributes("-topmost", True)     # stays on top of the desktop
root.configure(bg="#16181c")
def launch():
    subprocess.Popen([os.path.expanduser("~/rig_kiosk_launch.sh")])
btn = tk.Button(root, text="RIG\nKIOSK", command=launch,
    font=("DejaVu Sans", 52, "bold"), bg="#f5b428", fg="#16181c",
    activebackground="#ffcf57", relief="flat", bd=0, cursor="hand2")
btn.pack(fill="both", expand=True, padx=18, pady=18)
root.mainloop()
