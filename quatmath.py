"""Minimal, tested quaternion/matrix helpers (x,y,z,w order, ROS convention)."""
import numpy as np

def rodrigues(r):
    th = np.linalg.norm(r)
    if th < 1e-12: return np.eye(3)
    k = r/th; K = np.array([[0,-k[2],k[1]],[k[2],0,-k[0]],[-k[1],k[0],0]])
    return np.eye(3) + np.sin(th)*K + (1-np.cos(th))*(K@K)

def quat_from_matrix(R):
    """Shepperd's method, returns [x,y,z,w]."""
    t = np.trace(R)
    if t > 0:
        s = np.sqrt(t+1.0)*2; w = 0.25*s
        x = (R[2,1]-R[1,2])/s; y = (R[0,2]-R[2,0])/s; z = (R[1,0]-R[0,1])/s
    elif R[0,0] > R[1,1] and R[0,0] > R[2,2]:
        s = np.sqrt(1.0+R[0,0]-R[1,1]-R[2,2])*2; x = 0.25*s
        w = (R[2,1]-R[1,2])/s; y = (R[0,1]+R[1,0])/s; z = (R[0,2]+R[2,0])/s
    elif R[1,1] > R[2,2]:
        s = np.sqrt(1.0+R[1,1]-R[0,0]-R[2,2])*2; y = 0.25*s
        w = (R[0,2]-R[2,0])/s; x = (R[0,1]+R[1,0])/s; z = (R[1,2]+R[2,1])/s
    else:
        s = np.sqrt(1.0+R[2,2]-R[0,0]-R[1,1])*2; z = 0.25*s
        w = (R[1,0]-R[0,1])/s; x = (R[0,2]+R[2,0])/s; y = (R[1,2]+R[2,1])/s
    q = np.array([x,y,z,w]); return q/np.linalg.norm(q)

def matrix_from_quat(q):
    x,y,z,w = q / np.linalg.norm(q)
    return np.array([
        [1-2*(y*y+z*z), 2*(x*y-z*w),   2*(x*z+y*w)],
        [2*(x*y+z*w),   1-2*(x*x+z*z), 2*(y*z-x*w)],
        [2*(x*z-y*w),   2*(y*z+x*w),   1-2*(x*x+y*y)]])

def slerp(q0, q1, f):
    d = float(np.dot(q0, q1))
    if d < 0: q1 = -q1; d = -d
    if d > 0.9995:
        q = q0 + f*(q1-q0); return q/np.linalg.norm(q)
    th = np.arccos(np.clip(d,-1,1))
    return (np.sin((1-f)*th)*q0 + np.sin(f*th)*q1)/np.sin(th)
