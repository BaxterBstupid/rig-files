#!/usr/bin/env python3
"""Analyze L2 IMU ROS2 bag (.db3) on the Jetson. v2 - fixed CDR alignment.
CDR: 4-byte encapsulation header, then body. Alignment is relative to body start
(i.e. offset AFTER the 4-byte header). Doubles align to 8 within the body."""
import sys, sqlite3, numpy as np, struct

bag = sys.argv[1] if len(sys.argv)>1 else "/home/fasterbybaxter/l2_imu_check/l2_imu_check_0.db3"
con=sqlite3.connect(bag); cur=con.cursor()
cur.execute("SELECT id,name FROM topics")
imu_id=None
for tid,name in cur.fetchall():
    if 'imu' in name.lower(): imu_id=tid
cur.execute("SELECT data FROM messages WHERE topic_id=? ORDER BY timestamp",(imu_id,))
rows=cur.fetchall()
print("IMU messages:",len(rows))

def parse(buf):
    # body starts after 4-byte encapsulation header; track pos RELATIVE to body start
    base=4
    p=0  # position within body
    def align(n):
        nonlocal p
        r=p%n
        if r: p+=n-r
    def u32():
        nonlocal p; v=struct.unpack_from('<I',buf,base+p)[0]; p+=4; return v
    def i32():
        nonlocal p; v=struct.unpack_from('<i',buf,base+p)[0]; p+=4; return v
    def dbl(k):
        nonlocal p; align(8); v=struct.unpack_from('<%dd'%k,buf,base+p); p+=8*k; return v
    def skip(n):
        nonlocal p; p+=n
    sec=i32(); nsec=u32()
    slen=u32(); skip(slen)           # frame_id
    o=dbl(4)                          # orientation xyzw (aligns to 8 first)
    skip(72)                          # orientation_covariance 9 doubles
    g=dbl(3)                          # angular_velocity
    skip(72)
    a=dbl(3)                          # linear_acceleration
    return sec+nsec/1e9,o,g,a

t=[];O=[];G=[];A=[]
for (data,) in rows:
    try:
        tt,o,g,a=parse(bytes(data)); t.append(tt);O.append(o);G.append(g);A.append(a)
    except: pass
t=np.array(t);O=np.array(O);G=np.array(G);A=np.array(A)
N=len(t); print("parsed:",N)
ox,oy,oz,ow=O[:,0],O[:,1],O[:,2],O[:,3]
gx,gy,gz=G[:,0],G[:,1],G[:,2]; ax,ay,az=A[:,0],A[:,1],A[:,2]

# sanity: if accel mag isn't ~9.8, parse is still off
mag=np.sqrt(ax**2+ay**2+az**2)
print("\nSANITY accel mag mean %.3f (want ~9.8). quat norm mean %.4f (want ~1)"%(
    mag.mean(), np.sqrt(ox**2+oy**2+oz**2+ow**2).mean()))
if not (5<mag.mean()<15):
    print("  !! parse still off - accel not gravity-scale. Stop, report to Claude."); sys.exit()

dt=np.diff(t)
print("\n[1] RATE/DROPOUTS: %.1f Hz median; gaps>10ms %d (%.2f%%); max gap %.4fs"%(
    1/np.median(dt),np.sum(dt>0.01),100*np.sum(dt>0.01)/len(dt),dt.max()))
print("[2] GRAVITY axis mean: x %.2f y %.2f z %.2f (mag mean %.3f std %.3f)"%(
    ax.mean(),ay.mean(),az.mean(),mag.mean(),mag.std()))
qn=np.sqrt(ox**2+oy**2+oz**2+ow**2)
print("[3] QUAT norm mean %.4f std %.6f; #34-degenerate %d"%(
    qn.mean(),qn.std(),np.sum((np.abs(ox)<1e-6)&(np.abs(oy)<1e-6)&(np.abs(oz)<1e-6))))
gm=np.sqrt(gx**2+gy**2+gz**2)
qd=[]
for i in range(1,N,20):
    d=np.clip(abs(np.dot(O[i-1],O[i])),0,1); qd.append(2*np.arccos(d))
qd=np.array(qd)
print("[4] ORIENTATION TRACKS MOTION: gyro mean %.4f max %.4f rad/s; quat max step %.4f -> %s"%(
    gm.mean(),gm.max(),qd.max(),"LIVE tracks motion" if qd.max()>1e-3 else "FROZEN"))
print("[5] GYRO BIAS gx %.5f gy %.5f gz %.5f"%(gx.mean(),gy.mean(),gz.mean()))
