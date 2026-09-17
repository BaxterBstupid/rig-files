#!/usr/bin/env python3
"""validate_colmap.py -- catch the 'end of tape' malformations BEFORE importing to RealityScan.
Run: python3 validate_colmap.py <colmap_dir>   ->  PASS or lists exact problems."""
import sys,os
d=sys.argv[1] if len(sys.argv)>1 else '.'
problems=[]
# images.txt: must be EXACTLY 2 lines per image (pose + one blank/points2d)
raw=open(os.path.join(d,'images.txt'),'rb').read()
if b'\r' in raw: problems.append('images.txt has CR (\\r) bytes - use unix \\n only')
lines=raw.decode().split('\n')
# strip trailing empty from final newline
while lines and lines[-1]=='' : lines.pop()
hdr=[l for l in lines if l.startswith('#')]
body=lines[len(hdr):]
pose=[l for l in body if l[:1].isdigit()]
# after each pose line there must be exactly ONE line (blank or points2d) before the next pose
gaps=[]
bi=[i for i,l in enumerate(body) if l[:1].isdigit()]
for k in range(len(bi)-1):
    gaps.append(bi[k+1]-bi[k])
badgaps=[g for g in gaps if g!=2]
if badgaps: problems.append('images.txt: %d image(s) NOT 2-lines-per-image (gaps=%s) <-- THE END-OF-TAPE BUG'%(len(badgaps),set(badgaps)))
for l in body:
    if l!=l.rstrip(): problems.append('images.txt: trailing whitespace on a line'); break
# header count
import re
for h in hdr:
    m=re.search(r'Number of images:\s*(\d+)',h)
    if m and int(m.group(1))!=len(pose):
        problems.append('images.txt: header says %s images but body has %d'%(m.group(1),len(pose)))
# points3D.txt header-only
p3=open(os.path.join(d,'points3D.txt')).read().splitlines()
p3data=[l for l in p3 if l.strip() and not l.startswith('#')]
if p3data: problems.append('points3D.txt has %d data rows (want header-only for pose workflow)'%len(p3data))
# cameras.txt one line
cam=[l for l in open(os.path.join(d,'cameras.txt')).read().splitlines() if l.strip() and not l.startswith('#')]
if len(cam)<1: problems.append('cameras.txt has no camera line')
print('images:%d  cameras:%d  points3D-data:%d'%(len(pose),len(cam),len(p3data)))
if problems:
    print('*** FAIL ***'); [print('  -',p) for p in problems]; sys.exit(1)
print('*** PASS - well-formed for RealityScan known-pose import ***')
