"""THE CAPTURE TWIN: a synthetic fusioncap bag where EVERY estimated quantity is known.
- textured room (ground-truth geometry + colours, deliberate hole)
- trajectory with strong speed variation (tau needs correlation structure)
- /unilidar/cloud  (12 Hz, sensor frame)      } stamped on the LIDAR clock = t + TAU
- /aft_mapped_to_init (100 Hz, ground truth)  } (Point-LIO inherits the lidar clock)
- /image_raw (10 Hz, 320x240 rgb8) rendered through the KNOWN mount extrinsic,
  stamped on the CAMERA clock = t
TRUE_TAU = +0.180 s  (lidar LAGS camera - the Master's measured direction)"""
import numpy as np, sys, shutil, time
sys.path.insert(0, "/tmp/minework"); sys.path.insert(0, "/tmp/extwork")
from quatmath import quat_from_matrix
import synth                       # textured world + splat renderer + TRUE_EXTR
from rosbags.rosbag2 import Writer
from rosbags.typesys import Stores, get_typestore

TRUE_TAU = 0.180
DUR = 30.0
rng = np.random.default_rng(21)

def pose(t):
    """ellipse walk with speed modulation PLUS the human: hand tremor (1.5-4 Hz
    rotational jitter) and step bounce (~1.9 Hz vertical). This fast shared structure
    is what makes tau observable - a silk-smooth trajectory has no alignment texture."""
    s = t + 1.8*np.sin(0.9*t) + 0.9*np.sin(0.37*t + 1.0)
    th = s/60*2*np.pi
    tw = 2*np.pi*t
    p = np.array([3+1.8*np.cos(th), 2+1.1*np.sin(th),
                  1.4+0.08*np.sin(3*th) + 0.012*np.sin(1.9*tw) + 0.006*np.sin(3.3*tw+0.7)])
    jy = 0.011*np.sin(1.8*tw+1.1) + 0.007*np.sin(3.1*tw) + 0.004*np.sin(6.8*tw+0.5) + 0.0025*np.sin(9.2*tw+2.2)
    jp = 0.009*np.sin(2.4*tw+0.3) + 0.006*np.sin(4.1*tw+2.0) + 0.0035*np.sin(7.6*tw+1.4)
    # physiological tremor genuinely extends 6-12 Hz - it is what sharpens tau in the field
    R = synth.rodrigues([0,0,th+np.pi/2+0.8*np.sin(2*th)+jy]) @ synth.rodrigues([0,0.07*np.sin(1.7*th)+jp,0])
    return R, p

ts = get_typestore(Stores.ROS2_HUMBLE)
PC2=ts.types["sensor_msgs/msg/PointCloud2"]; PF=ts.types["sensor_msgs/msg/PointField"]
IMG=ts.types["sensor_msgs/msg/Image"]; Odom=ts.types["nav_msgs/msg/Odometry"]
Header=ts.types["std_msgs/msg/Header"]; Tm=ts.types["builtin_interfaces/msg/Time"]
Pose_=ts.types["geometry_msgs/msg/Pose"]; PoseCov=ts.types["geometry_msgs/msg/PoseWithCovariance"]
Pt=ts.types["geometry_msgs/msg/Point"]; Qt=ts.types["geometry_msgs/msg/Quaternion"]
Tw=ts.types["geometry_msgs/msg/Twist"]; TwCov=ts.types["geometry_msgs/msg/TwistWithCovariance"]
V3=ts.types["geometry_msgs/msg/Vector3"]
def stamp(t):
    s=int(t); return Tm(sec=s, nanosec=int((t-s)*1e9))

pts, cols = synth.make_world()
T0 = 2000.0
t_start = time.time()
shutil.rmtree("twinbag", ignore_errors=True)
with Writer("twinbag", version=8) as w:
    c_o = w.add_connection("/aft_mapped_to_init", Odom.__msgtype__, typestore=ts)
    c_c = w.add_connection("/unilidar/cloud", PC2.__msgtype__, typestore=ts)
    c_i = w.add_connection("/image_raw", IMG.__msgtype__, typestore=ts)
    # odometry (lidar clock: t + TAU)
    for i in range(int(DUR*100)):
        t=i/100.0; R,p=pose(t); q=quat_from_matrix(R)
        m=Odom(header=Header(stamp=stamp(T0+t+TRUE_TAU), frame_id="odom"), child_frame_id="body",
               pose=PoseCov(pose=Pose_(position=Pt(x=p[0],y=p[1],z=p[2]),
                                       orientation=Qt(x=q[0],y=q[1],z=q[2],w=q[3])), covariance=np.zeros(36)),
               twist=TwCov(twist=Tw(linear=V3(x=0,y=0,z=0), angular=V3(x=0,y=0,z=0)), covariance=np.zeros(36)))
        w.write(c_o, int((T0+t+TRUE_TAU)*1e9), ts.serialize_cdr(m, Odom.__msgtype__))
    # clouds (lidar clock)
    fields=[PF(name=n,offset=o,datatype=7,count=1) for n,o in (("x",0),("y",4),("z",8),("intensity",12))]
    for i in range(int(DUR*12)):
        t=i/12.0; R,p=pose(t)
        d2=((pts-p)**2).sum(1); near=np.flatnonzero(d2<25.0)
        pick=rng.choice(near, size=min(1800,len(near)), replace=False)
        Xs=(pts[pick]+rng.normal(0,0.008,(len(pick),3))-p)@R
        arr=np.zeros((len(Xs),4),"<f4"); arr[:,:3]=Xs; arr[:,3]=rng.uniform(0,255,len(Xs))
        m=PC2(header=Header(stamp=stamp(T0+t+TRUE_TAU), frame_id="unilidar_lidar"),
              height=1,width=len(arr),fields=fields,is_bigendian=False,point_step=16,
              row_step=16*len(arr),data=np.frombuffer(arr.tobytes(),np.uint8),is_dense=True)
        w.write(c_c, int((T0+t+TRUE_TAU+0.004)*1e9), ts.serialize_cdr(m, PC2.__msgtype__))
    # camera (CAMERA clock: t) through the known mount
    nimg=0
    for i in range(int(DUR*30)):
        t=i/30.0; R,p=pose(t)
        T=np.eye(4); T[:3,:3]=R; T[:3,3]=p
        img,_=synth.render(pts, cols, T)          # 640x480 through TRUE_EXTR
        small=(np.clip(img[::4,::4],0,1)*255).astype(np.uint8)   # 160x120 - 30 Hz needs small frames
        m=IMG(header=Header(stamp=stamp(T0+t), frame_id="camera"),
              height=small.shape[0], width=small.shape[1], encoding="rgb8",
              is_bigendian=0, step=small.shape[1]*3,
              data=np.frombuffer(small.tobytes(),np.uint8))
        w.write(c_i, int((T0+t+0.006)*1e9), ts.serialize_cdr(m, IMG.__msgtype__))
        nimg+=1
print(f"twinbag: {int(DUR*12)} clouds + {nimg} images + {int(DUR*100)} odom | TRUE_TAU={TRUE_TAU}s (lidar lags) | {time.time()-t_start:.0f}s to build")
