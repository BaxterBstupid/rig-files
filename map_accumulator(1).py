"""Bounded voxel accumulator for the live coverage map.
Streams of world-frame points go in; a capped, hit-counted voxel map comes out.
Pure numpy. Designed to be cheap enough to run BESIDE a recording capture:
- add_points() is O(batch) quantize+buffer only (called from the ROS callback)
- merge() folds buffered batches into the sorted master with searchsorted+insert,
  O(master) memmove, meant to be called every 1-2 s from the serve path
- memory is hard-capped: at max_voxels the map stops growing (capped flag set),
  but hit counts on existing voxels keep updating.
"""
import numpy as np, threading

_OFF = 1 << 20          # 21-bit signed field per axis
_FIELD = (1 << 21) - 1

class VoxelMap:
    def __init__(self, voxel=0.05, max_voxels=2_000_000):
        self.voxel = float(voxel)
        self.max_voxels = int(max_voxels)
        self.keys = np.empty(0, np.int64)
        self.pts = np.empty((0, 3), np.float32)
        self.counts = np.empty(0, np.int32)
        self.capped = False
        self.total_in = 0
        self._pending = []
        self._lock = threading.Lock()

    def add_points(self, xyz):
        """xyz: (N,3) float array in metres, world frame. Cheap; callback-safe."""
        if xyz is None or len(xyz) == 0: return
        q = np.floor(np.asarray(xyz, np.float64) / self.voxel).astype(np.int64)
        ok = np.all(np.abs(q) < _OFF, axis=1) & np.isfinite(xyz).all(axis=1)
        if not ok.any(): return
        q = q[ok]; p = np.asarray(xyz, np.float32)[ok]
        k = ((q[:,0]+_OFF) << 42) | ((q[:,1]+_OFF) << 21) | (q[:,2]+_OFF)
        with self._lock:
            self._pending.append((k, p))
            self.total_in += len(k)

    def merge(self):
        with self._lock:
            if not self._pending: return
            batches, self._pending = self._pending, []
        bk = np.concatenate([b[0] for b in batches])
        bp = np.concatenate([b[1] for b in batches])
        uk, ui, uc = np.unique(bk, return_index=True, return_counts=True)
        up = bp[ui]
        pos = np.searchsorted(self.keys, uk)
        exists = np.zeros(len(uk), bool)
        inb = pos < len(self.keys)
        exists[inb] = self.keys[pos[inb]] == uk[inb]
        if exists.any():
            np.add.at(self.counts, pos[exists], uc[exists].astype(np.int32))
        novel = ~exists
        if novel.any() and not self.capped:
            room = self.max_voxels - len(self.keys)
            if room <= 0:
                self.capped = True
            else:
                if novel.sum() > room:
                    idx = np.flatnonzero(novel)[:room]
                    sel = np.zeros(len(uk), bool); sel[idx] = True
                    novel = sel; self.capped = True
                ip = pos[novel]
                self.keys = np.insert(self.keys, ip, uk[novel])
                self.pts = np.insert(self.pts, ip, up[novel], axis=0)
                self.counts = np.insert(self.counts, ip, uc[novel].astype(np.int32))

    def snapshot(self, max_points=150_000):
        """(M,4) float32 [x,y,z,hit_count], every-kth downsample to <= max_points."""
        n = len(self.keys)
        if n == 0: return np.empty((0,4), np.float32)
        step = max(1, -(-n // max_points))
        out = np.empty((len(self.pts[::step]), 4), np.float32)
        out[:, :3] = self.pts[::step]
        out[:, 3] = self.counts[::step]
        return out

    def full_points_counts(self):
        return self.pts.copy(), self.counts.copy()

    def clear(self):
        with self._lock:
            self.keys = np.empty(0, np.int64); self.pts = np.empty((0,3), np.float32)
            self.counts = np.empty(0, np.int32); self.capped = False
            self.total_in = 0; self._pending = []
