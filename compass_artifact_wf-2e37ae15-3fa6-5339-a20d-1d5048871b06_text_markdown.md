# Running Unreal Engine 5 Interactively on Cloud GPU Desktops from a Windows Thin Client: A Grounded Decision Guide

## TL;DR
- **Your Vagon freeze is almost certainly a resources/timeout problem, not bad luck: the free trial runs on the Planet tier (Tesla T4, 4 vCPU, 16 GB RAM, 75 GB disk), which is underpowered for an Epic Games Launcher + UE5 install — Unreal's own guidance says to "plan for at least 80–120 GB including engine content." Give Vagon exactly ONE more try, but on Flame or Blaze (A10G, 32–64 GB RAM) with disk pre-expanded to ≥175 GB, before switching.**
- **iRender has the best raw price-performance (RTX 4090 node at $8.20/hr, real interactive UE5 via Parsec) BUT all its hardware is physically in Vietnam; a US user should expect roughly 150–250 ms round-trip latency — fine for batch rendering, a genuine handicap for tight interactive viewport work. Xesktop is batch-render-only (GTX 1080 Ti / V100, session-wiped U-drive storage) and unsuitable for interactive relighting/previz.**
- **Your LiDAR data will NOT import directly as PLY/PCD. Use free CloudCompare to convert: mesh PLY→FBX/OBJ, point cloud PCD/PLY→LAS/LAZ/E57 (UE5's LiDAR Point Cloud plugin reads .las, .e57, .pts, .ptx, .xyz). For day→night relighting, a camera-textured mesh with baked daytime lighting is NOT directly usable — de-light it into a flat albedo (free Agisoft De-Lighter) before UE5's dynamic lights will look right.**

## Key Findings

### 1. Vagon: verified specs and what the freeze actually is
Vagon's current published pricing (San Francisco-based company, founded 2019) has three hardware families:

- **RTX-enabled A10G Tensor Core GPUs (24 GB GPU):** Spark (4 cores, 16 GB RAM, $1.67/hr), Flame (8 cores, 32 GB RAM, $2.27/hr), Blaze (16 cores, 64 GB RAM, $3.57/hr), Lava (48 cores, 4×24 GB GPU, 192 GB RAM, $11.97/hr). Vagon's own blog (dated August 11, 2026) confirms "its Flame tier was listed at $2.27 per hour with 32 GB RAM and a 24 GB NVIDIA A10G GPU," and its region-prices page shows this tier pricing applies to the N. Virginia and Oregon (US) regions.
- **NVIDIA Tesla T4 GPUs (16 GB GPU):** Planet (4 cores, 16 GB RAM, $0.99/hr — the "Best Value" default and the trial tier), Star (16 cores, 64 GB RAM, $2.99/hr), Galaxy (48 cores, 4×16 GB GPU, 192 GB RAM, $8.99/hr).
- **CPU-only Intel:** Sand ($0.25/hr), Lake ($0.39/hr), Sea ($1.49/hr), Ocean ($4.59/hr).

**Disk/storage (verified from the live pricing page):** Default disk is **75 GB, included** with the mandatory storage subscription of **$7.99/month (Personal)** or $19.99/month (Premium, which adds 25 GB of "Vagon Files" cloud storage vs. 5 GB). You can add storage at **$5 per additional 50 GB**, up to a maximum of **525 GB**. Outbound data transfer is free for the first 10 GB/month, then $1.50 per additional 10 GB. (The "$8/month persistent storage" figure you recalled is essentially correct — it's $7.99/month.)

**The freeze:** Your two failures happened during the Epic Games Launcher / Unreal install stage. This matches independent complaints. A Product Hunt reviewer wrote that Vagon "just refuses to respond in simply opening the file (when the specs it boasts of should be leagues ahead of my pc) and then kicks me out asking for more money." Trustpilot's aggregated review summary notes users report "startup and shutdown times can be relatively long, occasionally taking 5–10 minutes." The most likely root causes for a hang specifically at UE install:
- **(a) The trial/Planet tier's 4 vCPU and 16 GB RAM** being saturated by the Epic installer's extraction/verification — below Epic's recommended spec (see below).
- **(b) The 75 GB default disk being too small.** Epic's UE5 install guidance advises planning for **"at least 80–120 GB including engine content"** (download alone is ~35–60 GB depending on components). A full disk mid-install produces exactly the "unresponsive" behavior you saw.
- **(c) Trial sessions having tight time/credit limits** that "kick you out" (the trial is only 1 hour of Planet usage).

Note that Epic officially recommends **32 GB of RAM and at least 8 GB of graphics RAM** for current UE5 development — so the 16 GB-RAM trial tier is under-spec on two axes at once.

### 2. iRender: cheapest real interactive UE5 — but Vietnam-only latency is the catch
iRender (irendering.net, also branded GPUHub), operated by iRender JSC Vietnam, is an IaaS "rent-a-whole-machine" service. It genuinely supports interactive UE5: you connect via **Parsec or RDP** to a full Windows desktop and "work as if you're sitting in front of a powerful workstation."

- **RTX 4090 node: $8.20/hour** (or $7.38/hr billed at 3+ hours). Verified specs per iRender's pricing page: 24 GB VRAM, **AMD Ryzen Threadripper PRO 3955WX @ 3.9–4.2 GHz, 256 GB RAM, 2 TB NVMe SSD**, Windows/Ubuntu. Newer RTX 5090 nodes are $10.80/hr.
- **Promotions:** iRender's pricing page states verbatim, **"For newly registered customers 100% bonus first charge within 24h"**; a 20% "Golden Hours" credit-back applies on weekends (10% standard, 12% weekday happy hours). iRender advertises stacked savings bringing effective cost to ~$3.50–4.00/hr — that combined figure is iRender's own marketing math.
- **Data center location — the decisive factor:** All of iRender's hardware is physically in **Vietnam** (Hanoi, in an FPT Telecom Tier III facility). No US/North American data center appears on any iRender page or in any independent review. The Singapore address on their site is a corporate registration, not a compute location. (iRender never affirmatively states it has *only* one location, so this is inferred from the absence of any other stated site.)
- **US latency:** iRender's own blog claims "15–30 ms" Parsec latency and the affiliated review site RadarRender claims "20–40 ms" — but those describe near-region Asian users, and RadarRender hosts sponsored iRender content, so treat both as marketing. There is **no verified US-based latency measurement** in any public source. Based on geography (Hanoi to US West Coast ≈13,000 km; fiber round-trip ~130 ms before routing) and analogous long-haul reports, a US user should realistically expect **~150–250 ms round-trip**. That is irrelevant to batch rendering (Movie Render Queue output is identical regardless of latency) but a real handicap for tight interactive work — viewport orbiting, keyframing, precise cursor work.

### 3. Xesktop: batch rendering only — not for your workflow
Xesktop (xesktop.com, a GarageFarm.NET/Copernicus Computing product) rents dedicated GPU servers at **$6–8/node/hour**: Server 1 is 10× GTX 1080 Ti (11 GB), Server 2 is 8× Tesla V100 (16 GB). These are **old, render-farm-oriented GPUs** optimized for Octane/Redshift/Cycles batch jobs, not real-time UE5 Lumen/Nanite. Critically, Xesktop's documented workflow requires storing all project files on a **network "U:" drive** — data on C:/Desktop is deleted after each session — which is clumsy for interactive iterative work. Data-center location is not clearly stated (parent GarageFarm operates in Europe/Poland). **Verdict: unsuitable for interactive UE5 relighting/previz.**

### 4. Other alternatives with US data centers
- **Paperspace CORE** (now owned by DigitalOcean): offers interactive GPU Windows desktops with US data centers — the most direct "interactive GPU desktop with US latency" competitor to Vagon, though its Windows desktop offering has narrowed under DigitalOcean; verify current availability/pricing directly.
- **Shadow (shadow.tech):** a full persistent Windows 11 cloud PC with US data centers. Per tech-insider.org (Aug 2026), **Shadow PC Neo runs $37.99/month (with a $30.39 promo for the first three months) and Shadow PC Power runs $54.99/month**; the Power tier is an **NVIDIA RTX A4500 (≈RTX 3070 Ti), 20 GB GPU VRAM, 28 GB RAM**. Good if usage is heavy and constant; the flat fee is wasteful for occasional bursts.
- **AWS/Azure GPU instances** (e.g., G4dn/G5 with T4/A10G) in US regions with Parsec one-click deploy: interactive-capable and low US latency, but $12–20/hr with data-center GPUs and 30–60 min manual setup.
- **vast.ai / RunPod:** very cheap RTX 4090 (as low as $0.16–0.53/hr on aggregators) but these are primarily Linux/AI-container marketplaces — a reliable interactive Windows GPU desktop is not their core product and is fiddly to set up.

### 5. LiDAR/mesh into Unreal — the format reality
**What UE5 imports:**
- **Meshes:** FBX, OBJ, USD/USDZ, glTF/GLB (Datasmith and Interchange also handle several CAD/DCC formats).
- **Point clouds (via the built-in LiDAR Point Cloud plugin, native since UE 4.25):** LAS, LAZ, E57, PTS, PTX, and ASCII XYZ/TXT. It does **NOT** import PLY or PCD point clouds directly.

**Free conversion path (CloudCompare, open-source):**
- **Mesh:** PLY → FBX or OBJ. CloudCompare loads OBJ, PLY, STL, FBX and exports between them via File → Save As.
- **Point cloud:** PCD/PLY/PTS → LAS/LAZ/E57. CloudCompare reads E57, LAS, PLY, PTS, PTX, XYZ and exports LAS/E57. (Blender or the command-line `e57-to-las` tool are backups.)
- Watch for: E57 color issues in UE (a documented bug — PTS sometimes imports colors correctly when E57 does not), and structured vs. unstructured E57 causing empty imports.

### 6. Relighting captured/photogrammetry meshes — the core limitation
This is the workflow's real gotcha. A camera-textured/photogrammetry mesh has the **daytime lighting, shadows, and ambient occlusion baked into its texture (or vertex colors)**. Drop that straight into UE5, add night lighting, and the baked daytime highlights and shadows will fight your new lights and look wrong.

- **Per-vertex-color meshes are essentially unusable for quality relighting.** UE treats vertex colors as data, not a proper albedo; you get no UV-mapped texture detail and the baked lighting is locked in. You need a **UV-unwrapped mesh with a de-lit albedo (base color) texture**.
- **De-lighting workflow (free tools):** Export the base color map from your photogrammetry software, then remove baked lighting with **Agisoft De-Lighter** — per CG Channel, "a free standalone tool for removing baked-in lighting from the texture maps of 3D models generated through photogrammetry... based on the built-in de-lighting functionality in Metashape" — or the **Unity De-Lighting Tool** (free, open-source; requires the lit texture plus AO, normal, and bent-normal maps, bakeable in xNormal/Knald/Substance). Epic's own "Imperfection for Perfection" guide describes the manual method: recreate the capture-day lighting in a 3D app, bake that lighting, then divide the original texture by it to recover a flat albedo (roughly `Original / (Baked Lighting × 5) = Delighted Texture`).
- Once you have a flat albedo, build a standard PBR material in UE5 (albedo + normal + roughness), enable Nanite for the dense mesh, and UE5's dynamic Lumen lights will relight it convincingly for day→night previz.

## Details / Cost Comparison

| Option | GPU | Interactive UE5? | US latency | Rough cost | Best for |
|---|---|---|---|---|---|
| Vagon Flame/Blaze | A10G 24 GB | Yes (browser/app stream) | Low (US data centers: N. Virginia, Oregon) | $2.27–3.57/hr + $7.99/mo | Your use case, if install completes |
| iRender | RTX 4090 24 GB (Threadripper, 256 GB RAM) | Yes (Parsec/RDP) | ~150–250 ms (Vietnam) | $8.20/hr (bonuses lower it) | Batch render; borderline interactive |
| Xesktop | GTX 1080 Ti / V100 | Batch only | Unclear (EU?) | $6–8/hr | Offline GPU rendering, not you |
| Shadow | RTX A4500 (~3070 Ti), 20 GB | Yes (full PC) | Low (US) | $37.99 / $54.99 per month flat | Heavy constant use |
| AWS/Azure G5 | A10G/T4 | Yes (Parsec) | Low (US) | $12–20/hr | Tech-comfortable users |
| Paperspace CORE | Various RTX | Yes | Low (US) | Check current | Vagon alternative |

## Recommendations

**Stage 1 — Give Vagon one properly-configured try (do this first).** The evidence points to under-provisioning, not a fundamental "Vagon can't run UE" problem. Before launching:
1. Choose **Flame ($2.27/hr, A10G, 8 cores, 32 GB RAM)** or **Blaze ($3.57/hr, 64 GB RAM)** — NOT Planet/Spark. This meets Epic's recommended 32 GB RAM / ≥8 GB VRAM spec; Planet's 16 GB RAM does not.
2. **Pre-expand the disk to 175 GB** (75 GB base + $10/mo for +100 GB) *before* installing, so the Epic Launcher + UE5 (plan for 80–120 GB) + your mesh data never hit a full disk mid-install.
3. Install via Vagon's **preinstalled-apps library** if UE/Epic Launcher is offered there (avoids the manual installer hang), or install the Epic Launcher and let UE finish downloading fully before opening any project.
4. Run Vagon's connection performance test first; use the desktop app (not just the browser) and a wired connection from your thin client.

**Benchmark that changes this:** if a properly-specced Flame/Blaze session with a ≥175 GB disk *still* hangs at install after ~15 minutes, stop paying Vagon and move to Stage 2.

**Stage 2 — If Vagon fails again, switch based on how interactive you truly need to be:**
- If your work is **mostly setup + batch relit renders** (place cameras, trigger Movie Render Queue, download stills/sequences), **iRender is the best value** — the ~150–250 ms latency doesn't affect render output, and the RTX 4090 + 100% first-deposit bonus is cheap. Accept laggy viewport navigation as the trade-off.
- If you need **fluid real-time viewport interaction** with US latency, use **Paperspace CORE** or a **Parsec-on-AWS/Azure G5** instance. If your usage becomes heavy and constant, **Shadow's flat $37.99–54.99/month** may beat per-hour billing.
- **Do not use Xesktop** for this — its GPUs and session-wiped U-drive workflow are built for offline batch rendering.

**Stage 3 — Data pipeline (do this regardless of host):**
1. In **CloudCompare**: convert mesh PLY→FBX/OBJ; convert point cloud PCD/PLY→LAS or E57.
2. In UE5: import meshes normally; import point clouds via the **LiDAR Point Cloud plugin** (enable it first).
3. For relighting: **de-light your textured mesh** with Agisoft De-Lighter (free) to get a flat albedo, UV-unwrap if needed, then build a PBR material and light dynamically. Budget real time for this — it is the step most likely to make or break your day→night previz.

## Caveats
- **iRender's US latency (~150–250 ms) is an inference from geography and analogous long-haul reports, not a verified US-user measurement.** The only way to know for certain is to create an account (they have a 100% first-deposit bonus), connect via Parsec from your location, and check the ping. iRender's own "15–40 ms" figures are for near-region users and should not be trusted for the US.
- Vagon's exact GPU-per-tier (A10G vs T4) and disk pricing are from Vagon's live pricing page and blog, current as of this research; region-based pricing can vary and only some regions (e.g., N. Virginia, Oregon) carry the full A10G tier lineup.
- Vagon review sentiment is genuinely mixed and polarized (Trustpilot ~3.9, with scam-adviser flags about billing confusion and the mandatory monthly storage fee stacked on top of pay-per-use). The specific "unresponsive at install" failure is reported by individual users but is not documented by Vagon as a known bug — the root cause here (tier/disk/timeout) is inferred, not officially confirmed.
- Paperspace CORE's Windows-desktop offering has changed under DigitalOcean; verify current availability/pricing before committing.
- The de-lighting step assumes you have (or can export) a UV-textured base color map from your capture software. If your capture only produced a vertex-colored mesh with no UVs, you must UV-unwrap and bake vertex colors to a texture first (CloudCompare/Blender/Instant Meshes), adding a step.
- The search-tool outage recurred during this run (the live search budget was exhausted early by timeouts), so some secondary confirmations — e.g., a dedicated Reddit thread reproducing the exact "unresponsive at Epic install" failure, and current Paperspace CORE Windows pricing — could not be independently pulled and remain the thinnest-sourced points.