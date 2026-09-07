#!/usr/bin/env python3
"""TAU from a dump_curves CSV (kind,stamp,a,b). Reuses tau_solve.py's vetted
zs/hp/solve math; only the INPUT changes (CSV series instead of bag+odom).
Solves CAM vs each of {IMU, LID-arrival, LID-capture(col b)}."""
import sys, csv, numpy as np

def zs(x):
    r = np.empty(len(x)); r[np.argsort(x)] = np.arange(len(x)); r /= max(len(x)-1,1)
    return (r - r.mean())/(r.std()+1e-9)

def hp(x, dt=0.02, sigma_s=0.4):
    n = int(4*sigma_s/dt) | 1
    k = np.exp(-0.5*((np.arange(n)-n//2)*dt/sigma_s)**2); k/=k.sum()
    return x - np.convolve(x, k, mode="same")

def solve(a_t,a_v,b_t,b_v, max_lag=0.6, grid=0.005):
    if len(a_t)<10 or len(b_t)<10: return float('nan'),0.0,float('inf'),None
    lo=max(a_t.min(),b_t.min())+max_lag; hi=min(a_t.max(),b_t.max())-max_lag
    if hi-lo<3.0: return float('nan'),0.0,float('inf'),None
    tt=np.arange(lo,hi,0.02)
    A=zs(hp(np.interp(tt,a_t,a_v)))
    lags=np.arange(-max_lag,max_lag+1e-9,grid)
    corr=np.array([float(np.dot(A, zs(hp(np.interp(tt+L,b_t,b_v)))))/len(tt) for L in lags])
    i=int(np.argmax(corr))
    if 0<i<len(lags)-1:
        y0,y1,y2=corr[i-1],corr[i],corr[i+1]; d=(y0-y2)/(2*(y0-2*y1+y2)+1e-12); tau=lags[i]+d*grid
    else: tau=lags[i]
    width=(corr>=0.5*corr[i]).sum()*grid
    return tau,float(corr[i]),width,(lags,corr)

def gate(a_t,a_v,b_t,b_v,label):
    tau,peak,width,_=solve(a_t,a_v,b_t,b_v)
    if not np.isfinite(tau):
        print(f"  {label}: INSUFFICIENT OVERLAP (<3s) — no estimate"); return
    lo=max(a_t.min(),b_t.min()); hi=min(a_t.max(),b_t.max()); mid=0.5*(lo+hi)
    mA=a_t<mid; mB=a_t>=mid
    tA=solve(a_t[mA],a_v[mA],b_t,b_v)[0]; tB=solve(a_t[mB],a_v[mB],b_t,b_v)[0]
    halves=abs(tA-tB) if (np.isfinite(tA) and np.isfinite(tB)) else float('inf')
    ok = width<0.100 and halves<0.030
    print(f"  {label}: tau {tau*1000:+.1f} ms | peak {peak:.2f} | width {width*1000:.0f}ms(<100) | halves {halves*1000:.1f}ms(<30) -> {'PASS' if ok else 'WEAK'}")

def load(path):
    rows={'CAM':[], 'IMU':[], 'LID':[]}
    with open(path) as f:
        rd=csv.reader(f); next(rd)
        for r in rd:
            if len(r)<4: continue
            k=r[0]
            if k in rows: rows[k].append((float(r[1]),float(r[2]),float(r[3])))
    return {k:np.array(v) for k,v in rows.items()}

# ---------------- SANDBOX SELFTEST: inject a KNOWN lag, must recover it ----------------
def selftest():
    print("=== SELFTEST: inject known lag, must recover ===")
    rng=np.random.default_rng(0)
    T=40.0; base_t=np.sort(rng.uniform(0,T,4000))
    sig=np.cumsum(rng.standard_normal(len(base_t)))         # a wandering motion signal
    sig=sig-np.convolve(sig,np.ones(50)/50,mode='same')     # give it fast structure
    for true_lag in (0.175, -0.090, 0.000):
        # signal A samples at cam-rate, B is the SAME signal shifted by true_lag, odom-rate
        a_t=np.sort(rng.uniform(1,T-1,380)); a_v=np.interp(a_t,base_t,sig)
        b_t=np.sort(rng.uniform(1,T-1,3000)); b_v=np.interp(b_t+true_lag,base_t,sig)
        tau,peak,width,_=solve(a_t,a_v,b_t,b_v)
        err=(tau-true_lag)*1000
        print(f"  injected {true_lag*1000:+.0f}ms -> recovered {tau*1000:+.1f}ms  (err {err:+.1f}ms, peak {peak:.2f}, width {width*1000:.0f}ms)  {'OK' if abs(err)<10 else 'FAIL'}")

if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="--selftest": selftest(); sys.exit(0)
    d=load(sys.argv[1])
    cam=d['CAM']; imu=d['IMU']; lid=d['LID']
    print(f"loaded CAM {len(cam)} | IMU {len(imu)} | LID {len(lid)}")
    print("CAM vs each LiDAR-side signal (tau = lag aligning them):")
    if len(imu): gate(cam[:,0],cam[:,1], imu[:,0], imu[:,1], "CAM vs IMU (axis a)")
    if len(imu): gate(cam[:,0],cam[:,1], imu[:,0], imu[:,2], "CAM vs IMU (axis b)")
    if len(lid): gate(cam[:,0],cam[:,1], lid[:,0], lid[:,1], "CAM vs LID (arrival stamp)")
    if len(lid): gate(cam[:,0],cam[:,1], lid[:,2], lid[:,1], "CAM vs LID (CAPTURE stamp, col b)")
