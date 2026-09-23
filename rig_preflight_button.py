#!/usr/bin/env python3
import tkinter as tk, subprocess, os
root = tk.Tk()
root.title("RIG PRE-FLIGHT")
root.geometry("420x420+920+40")
root.attributes("-topmost", True)
root.configure(bg="#16181c")
def launch():
    subprocess.Popen([
        "gnome-terminal", "--title=RIG PRE-FLIGHT", "--",
        "bash", "-c", "$HOME/rig_start_lean.sh; echo; read -p 'Rig running - leave open. Ctrl-C the script to stop the rig.'"
    ])
btn = tk.Button(root, text="RIG\nPRE-FLIGHT", command=launch,
    font=("DejaVu Sans", 44, "bold"), bg="#4aa8ff", fg="#16181c",
    activebackground="#7cc2ff", relief="flat", bd=0, cursor="hand2")
btn.pack(fill="both", expand=True, padx=18, pady=18)
root.mainloop()
