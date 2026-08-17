from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2, Imu
import numpy as np, sys
r=SequentialReader(); r.open(StorageOptions(uri=sys.argv[1],storage_id='sqlite3'),ConverterOptions('',''))
ch=[]; ih=[]
while r.has_next():
    t,d,ts=r.read_next()
    if t=='/unilidar/cloud':
        m=deserialize_message(d,PointCloud2); ch.append(m.header.stamp.sec+m.header.stamp.nanosec*1e-9)
    elif t=='/unilidar/imu':
        m=deserialize_message(d,Imu); ih.append(m.header.stamp.sec+m.header.stamp.nanosec*1e-9)
ch=np.array(ch); ih=np.array(ih)
dc=np.diff(ch)*1000; di=np.diff(ih)*1000
print('CLOUD intervals ms: mean=%.1f std=%.1f min=%.1f max=%.1f'%(dc.mean(),dc.std(),dc.min(),dc.max()))
print('  first 15:',[round(x,1) for x in dc[:15]])
print('IMU intervals ms: mean=%.2f std=%.2f min=%.2f max=%.2f'%(di.mean(),di.std(),di.min(),di.max()))
print('IMU big gaps >20ms:', int((di>20).sum()), ' CLOUD irregular >100ms:', int((dc>100).sum()))
