#!/usr/bin/env python3
"""fix_images_txt.py -- SAFE repair of a corrupted COLMAP images.txt (the 'end of tape' 3-blank-line bug).
Reads the file FULLY into memory first (no truncate-before-read), keeps header + pose lines,
writes EXACTLY one blank line after each pose line = correct 2-lines-per-image COLMAP format.
Run on Shadow:  python fix_images_txt.py colmap_163005_key\\images.txt
"""
import sys
path = sys.argv[1] if len(sys.argv)>1 else 'images.txt'
data = open(path, 'r').read()            # read fully, then file closes
lines = data.split('\n')
header = [l for l in lines if l.startswith('#')]
poses  = [l.rstrip() for l in lines if l[:1].isdigit()]   # pose lines only, no trailing ws
out = list(header)
for p in poses:
    out.append(p)
    out.append('')                        # exactly ONE blank POINTS2D line
open(path, 'w', newline='\n').write('\n'.join(out).rstrip('\n') + '\n')
print("fixed %s: %d images, 2 lines each (%d total lines)" % (path, len(poses), len(header)+len(poses)*2))
