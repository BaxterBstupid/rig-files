#!/usr/bin/env python3
"""Analyze a recorded L2 IMU ROS2 bag (.db3) directly on the Jetson.
Reports rate, dropouts, orientation-tracks-motion, quaternion stability, gravity axis.
Reads the sqlite3 .db3 directly - no rosbag2 API needed."""
import sys, sqlite3, numpy as np

bag = sys.argv[1] if len(sys.argv)>1 else \
    "/home/fasterbybaxter/l2_imu_check/l2_imu_check_0.db3"

con=sqlite3.connect(bag); cur=con.cursor()
# find the imu topic id
cur.execute("SELECT id,name,type FROM topics")
topics=cur.fetchall()
imu_id=None
for tid,name,typ in topics:
    if 'imu' in name.lower(): imu_id=tid; imu_name=name
print("topics in bag:", [(n,t.split('/')[-1]) for _,n,t in topics])
if imu_id is None:
    print("no imu topic found!"); sys.exit(1)

cur.execute("SELECT timestamp,data FROM messages WHERE topic_id=? ORDER BY timestamp",(imu_id,))
rows=cur.fetchall()
print("IMU messages:",len(rows))

# --- parse sensor_msgs/Imu CDR payload ---
# CDR layout after 4-byte encapsulation header:
#   Header: stamp(sec int32, nanosec uint32), frame_id(string) [+padding]
#   orientation: 4x float64 (x,y,z,w)
#   orientation_cov: 9x float64
#   angular_velocity: 3x float64
#   angular_velocity_cov: 9x float64
#   linear_acceleration: 3x float64
#   linear_acceleration_cov: 9x float64
def parse_imu(buf):
    import struct
    off=4  # skip CDR encapsulation header
    sec,=struct.unpack_from('<i',buf,off); off+=4
    nsec,=struct.unpack_from('<I',buf,off); off+=4
    slen,=struct.unpack_from('<I',buf,off); off+=4
    off+=slen  # frame_id string
    # align to 8 for the double array
    if off%8: off+=8-(off%8)
    vals=struct.unpack_from('<4d',buf,off); off+=32  # orientation xyzw
    off+=72  # orientation cov 9d
    ang=struct.unpack_from('<3d',buf,off); off+=24
    off+=72
    lin=struct.unpack_from('<3d',buf,off); off+=24
    return sec+nsec/1e9, vals, ang, lin

t=[];ox=[];oy=[];oz=[];ow=[];gx=[];gy=[];gz=[];ax=[];ay=[];az=[]
for ts,data in rows:
    try:
        tt,o,g,a=parse_imu(bytes(data))
        t.append(tt);ox.append(o[0]);oy.append(o[1]);oz.append(o[2]);ow.append(o[3])
        gx.append(g[0]);gy.append(g[1]);gz.append(g[2]);ax.append(a[0]);ay.append(a[1]);az.append(a[2])
    except Exception as e:
        pass
t=np.array(t);ox=np.array(ox);oy=np.array(oy);oz=np.array(oz);ow=np.array(ow)
gx=np.array(gx);gy=np.array(gy);gz=np.array(gz);ax=np.array(ax);ay=np.array(ay);az=np.array(az)
N=len(t); print("parsed:",N)
if N<10: print("parse failed - CDR layout may differ"); sys.exit(1)

dt=np.diff(t)
print("\n[1] RATE / DROPOUTS")
print("  median dt %.5f s = %.1f Hz"%(np.median(dt),1/np.median(dt)))
print("  dt min/max %.5f / %.5f"%(dt.min(),dt.max()))
print("  gaps >10ms: %d (%.2f%%)"%(np.sum(dt>0.01),100*np.sum(dt>0.01)/len(dt)))
print("  largest gap: %.4f s"%dt.max())

mag=np.sqrt(ax**2+ay**2+az**2)
print("\n[2] ACCEL / GRAVITY")
print("  mag mean %.3f std %.3f (min %.2f max %.2f)"%(mag.mean(),mag.std(),mag.min(),mag.max()))
print("  gravity axis (mean): x %.2f y %.2f z %.2f"%(ax.mean(),ay.mean(),az.mean()))

qn=np.sqrt(ox**2+oy**2+oz**2+ow**2)
print("\n[3] QUATERNION")
print("  norm mean %.4f std %.6f (min %.4f max %.4f)"%(qn.mean(),qn.std(),qn.min(),qn.max()))
print("  #34-degenerate (x,y,z~0): %d"%np.sum((np.abs(ox)<1e-6)&(np.abs(oy)<1e-6)&(np.abs(oz)<1e-6)))

gyro_mag=np.sqrt(gx**2+gy**2+gz**2)
qd=[]
for i in range(1,N,20):
    q1=np.array([ox[i-1],oy[i-1],oz[i-1],ow[i-1]]);q2=np.array([ox[i],oy[i],oz[i],ow[i]])
    d=np.clip(abs(np.dot(q1,q2)),0,1); qd.append(2*np.arccos(d))
qd=np.array(qd) if qd else np.array([0])
print("\n[4] ORIENTATION TRACKS MOTION?")
print("  gyro mag: mean %.4f max %.4f rad/s (nonzero = you moved it)"%(gyro_mag.mean(),gyro_mag.max()))
print("  orientation max step %.4f rad -> %s"%(qd.max(),
      "LIVE, tracks motion" if qd.max()>1e-3 else "FROZEN (problem)"))
print("\n[5] GYRO BIAS: gx %.5f gy %.5f gz %.5f rad/s"%(gx.mean(),gy.mean(),gz.mean()))
