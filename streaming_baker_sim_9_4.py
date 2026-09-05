#!/usr/bin/env python3
# STREAMING baker memory sandbox: prove peak RAM stays BOUNDED (flat) across a full 2200-frame walk,
# vs the all-at-once baker that grows until lock. Models ALL THREE consumers, allocates to MEASURE.
import numpy as np, resource, gc, time

def rss_mb(): return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024

JETSON_USABLE_MB = 6500
SANDBOX_HARDCAP_MB = 2800   # abort before locking THIS 4GB box

# ---- the FULL walk parameters (180551, real) ----
TOTAL_FACES  = 715_316
TOTAL_IMGS   = 2_200
IMG_H, IMG_W = 1200, 1920           # real frame size
IMG_MB       = IMG_H*IMG_W*3/1e6    # one decoded frame ~= 6.9 MB

print("=== MODEL A: ALL-AT-ONCE (the baker that LOCKED) — estimate only, do NOT allocate ===")
allimg_mb   = TOTAL_IMGS * IMG_MB
score_mb    = TOTAL_FACES * TOTAL_IMGS * 4 / 1e6
mesh_mb     = TOTAL_FACES * (3*4 + 3*8) / 1e6
total_a     = allimg_mb + score_mb + mesh_mb
print(f"  all images resident : {allimg_mb:8.0f} MB")
print(f"  faces x imgs score  : {score_mb:8.0f} MB")
print(f"  mesh arrays         : {mesh_mb:8.0f} MB")
print(f"  TOTAL PEAK          : {total_a:8.0f} MB  ({total_a/1024:.1f} GB)")
print(f"  vs Jetson usable ~{JETSON_USABLE_MB} MB -> {'LOCKS (matches reality)' if total_a>JETSON_USABLE_MB else 'fits'}")
print()

print("=== MODEL B: STREAMING (chunked) — ALLOCATE each chunk, measure PEAK, free between ===")
print("  strategy: process faces in chunks; hold only CHUNK_IMGS images + one face-chunk score at a time")
base = rss_mb()
for CHUNK_FACES, CHUNK_IMGS in [(50_000, 8), (100_000, 12), (50_000, 20)]:
    n_chunks = -(-TOTAL_FACES // CHUNK_FACES)   # ceil
    peak = 0.0
    ok = True
    for c in range(min(n_chunks, 6)):   # simulate first 6 chunks (enough to show it's FLAT)
        # resident images for this chunk
        imgs = [np.zeros((IMG_H,IMG_W,3), np.uint8) for _ in range(CHUNK_IMGS)]
        # score buffer for this face-chunk vs its resident images
        score = np.zeros((CHUNK_FACES, CHUNK_IMGS), np.float32); score += 1.0
        cur = rss_mb() - base
        peak = max(peak, cur)
        if rss_mb() > SANDBOX_HARDCAP_MB:
            print(f"  chunk={CHUNK_FACES//1000}k faces / {CHUNK_IMGS} imgs -> HIT SANDBOX CAP, abort"); ok=False
            del imgs, score; gc.collect(); break
        del imgs, score; gc.collect()   # <-- the key: free before next chunk
    chunk_est = CHUNK_IMGS*IMG_MB + CHUNK_FACES*CHUNK_IMGS*4/1e6
    verdict = "FITS Jetson (bounded)" if chunk_est < 4000 else "too big"
    if ok:
        print(f"  chunk={CHUNK_FACES//1000}k faces / {CHUNK_IMGS:>2} imgs -> measured PEAK {peak:6.0f} MB, "
              f"est/chunk {chunk_est:5.0f} MB, {n_chunks} chunks total -> {verdict}")
print()
print("=== THE POINT ===")
print("  All-at-once peak GROWS with total frames -> unbounded -> LOCK.")
print("  Streaming peak = ONE chunk's cost, CONSTANT regardless of 2200 total frames -> BOUNDED.")
print("  If measured PEAK stays flat & small across chunks above, onboard streaming bake is VIABLE.")
