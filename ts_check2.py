from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2
import numpy as np, sys
r=SequentialReader(); r.open(StorageOptions(uri=sys.argv[1],storage_id='sqlite3'),ConverterOptions('',''))
ch=[]
while r.has_next():
    t,d,ts=r.read_next()
    if t=='/unilidar/cloud':
        m=deserialize_message(d,PointCloud2); ch.append(m.header.stamp.sec+m.header.stamp.nanosec*1e-9)
ch=np.array(ch); dc=np.diff(ch)*1000
# separate 'normal' intervals from 'gap' intervals
normal=dc[dc<150]  # clean scan-to-scan
gaps=dc[dc>=150]   # dropouts
print("NORMAL intervals (dropout-free): count=%d mean=%.1fms std=%.2fms"%(len(normal),normal.mean(),normal.std()))
print("  -> if std is tiny (~1-2ms), SDK stamping is CLEAN; gaps are recorder drops")
print("GAP intervals (dropouts): count=%d values(ms)=%s"%(len(gaps),[int(x) for x in sorted(gaps)]))
# are gaps ~integer multiples of 83ms? (= N dropped scans) or random?
print("gaps / 83.3ms =", [round(x/83.3,1) for x in sorted(gaps)])
print("  -> if near-integers, gaps = whole dropped scans (recorder), not stamp bug")
