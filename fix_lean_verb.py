f = "rig_kiosk_server.py"
s = open(f).read()
old = '''    "capture": os.path.expanduser("~/point_lio_capture.sh"),
}'''
if old not in s:
    print("ANCHOR NOT FOUND — no change made"); raise SystemExit
if "start_lean" in s:
    print("start_lean already present — no double-insert"); raise SystemExit
new = '''    "capture":    os.path.expanduser("~/point_lio_capture.sh"),
    "start_lean": os.path.expanduser("~/rig_start_lean.sh"),
}'''
s = s.replace(old, new)
open(f, "w").write(s)
print("ADDED start_lean verb to SCRIPTS.")
