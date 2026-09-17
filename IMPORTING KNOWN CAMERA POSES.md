# Importing Known Camera Poses (XMP Pose-Priors) + a Separate LiDAR Cloud into RealityScan 2.1 to Produce a Textured Mesh

## TL;DR
- **Your XMP design is correct in principle:** RealityScan reads `xcr:Rotation` as a **row-major, world-to-camera** matrix and `xcr:Position` as the **camera center** in world coordinates, applied as `m = R·(Xw − C)` — exactly what you built. Place same-basename `.xmp` next to each PNG, drag both in (or **Workflow → Add Folder**), confirm a **pin icon** appears on every image, enable camera priors in Alignment Settings, then run **Align Images** (F6). Locked poses are preserved, and alignment is still needed to build the component and triangulate tie points.
- **The crux — merging with LiDAR — works because both live in the same metric frame, but is not fully automatic.** Import the `.ply` as a **laser scan / LiDAR** and set registration to **"Exact – use existing registration"** so the imported geometry keeps its coordinates and defines the scene's coordinate system; then Align so cameras and cloud land in **one component**. If they land in two components, bridge them with **control points** (≥3 shared points). Then set a reconstruction region, **Calculate Model**, and **Texture** from the images.
- **The single most dangerous gotcha is the rotation-axis convention, not the math you already validated.** RealityScan's world frame is right-handed Z-up; camera conventions coming from an OpenCV/COLMAP-style pipeline (camera looks +Z, +Y down) frequently import "looking outward / mirrored," requiring an axis-basis change (row swap + sign flips) on R — **NOT a transpose.** Also verify `FocalLength35mm` = **(f_pixels ⁄ image_width) × 36**, and beware a **confirmed XMP-orientation regression in RealityScan 2.1.1** acknowledged by Epic staff with a promised hotfix.

---

## Key Findings

1. **XMP auto-load is real and vendor-documented.** Per RealityScan Help: *"If the XMP files are in the same folder as the images, the images will use the data stored in them when imported… All information from the XMP file will automatically be assigned to the corresponding image."* The file must share the image basename (`Image01.jpg` ↔ `Image01.xmp`). A **pin icon** next to each thumbnail confirms the pose loaded.

2. **`PosePrior="locked"` is the right choice and is preserved through alignment.** RealityScan Help ("Camera Priors" page) defines Locked verbatim as *"Locked – no changes in camera position allowed"* (both relative and absolute fixed). A practitioner who initially used `PosePrior="initial"` had cameras dropped/re-solved; Epic staff told him to switch to `locked`, after which *"all the cameras are there."* You still press **Align Images** — alignment with locked poses computes tie points/structure without moving the cameras.

3. **Rotation convention — definitively confirmed.** `xcr:Rotation` is the world→camera rotation, **row-major**, applied directly (not transposed): a world point projects via `m = R·(Xw − C)`, and internally `t = −R·C` (equivalently `C = −Rᵀ·t`, identical to COLMAP's `-Rᵀ·T` camera-center relation). This was verified numerically by user JesseJiang010 in the Epic forum thread "Camera Parameters in the output XMP file" (Sept 10, 2024), who confirmed after implementing the "RealityCapture XMP Camera Math" KB math: *"It's working perfectly, showing the exact pixel position in Reality Capture!"* His working code uses `t = −R·position` and `focal = FocalLength35mm × sensor_width / 36`. Your exporter's convention (world-to-camera row-major R + camera-center position) matches.

4. **Combining posed images with a separately-imported LiDAR cloud in one metric frame is a supported 2.1 workflow but has friction.** RealityScan 2.1 documentation states: *"Import the point cloud and generate virtual cameras based on camera pose priors or an imported component from a Colmap scene. Combine with photogrammetry or other LiDAR data."* For an already-registered cloud, import it as a laser scan with **Exact** registration so *"the imported poses will be unchanged. In this case the imported model defines the coordinate system."*

5. **Meshing from LiDAR + texturing from images is a standard, documented sequence.** Once inputs share one component: define a reconstruction region → **Calculate Model** (mesh) → **Texture**. RealityScan treats LiDAR `.lsp` and images identically after import (*"continue like if the imported LiDAR scans were ordinary images"*). The DotProduct/Dot3D KB confirms the real click sequence: laser-scan import (Exact) → Align → High-detail model → Texture (*"RC uses the images to project a texture on the 3D model"*).

6. **There are named, confirmed failure modes.** RealityScan 2.1 documentation lists as known issues, verbatim: *"Using LSP files in components significantly slows down alignment with images"* and *"Calibration or lens group is not accepted when importing images with corresponding XMP files."* Separately, an XMP-orientation regression is acknowledged in 2.1.1 (see §6).

---

## Details

### 1. The exact GUI workflow for XMP pose import

**Confirmed click-sequence (vendor docs + practitioner posts):**
1. Put every `.xmp` in the same folder as its PNG, same basename. (Optional: a single `_common.xmp` in the folder applies shared fields to all images; per-image files are what you have.)
2. **Add the images** — drag-and-drop the folder into the app, or **Workflow → Add Folder** (adds all) / **Add Images**. Either works; Add Folder is least fiddly for 422 files. XMP is consumed automatically on import; there is no separate "import XMP" GUI command.
3. **Verify the pin icon** appears on each image (documented visual confirmation the pose/priors were read).
4. In **Alignment Settings**, ensure priors are actually used — RealityScan's help notes you must enable camera priors for the stored data to be honored, and for locked poses confirm the pose-prior "hardness"/accuracy is set to respect them.
5. Press **Align Images** (F6). With `PosePrior="locked"`, cameras stay fixed; alignment forms the component and triangulates tie points needed later.

**Do you skip alignment?** No. Even with locked poses, you must Align to (a) form a *component* (the object meshing/texturing consume) and (b) generate tie points. Locked simply means Align won't move your cameras.

**Draft vs High/normal alignment:** Locked poses don't need high-accuracy matching to *find* the cameras (they're given), but you still need enough feature matching to co-register the LiDAR and images if relying on features (§4). Normal alignment is the safe default; Draft is only for fast previews.

### 2. Verifying the poses loaded correctly

- **Pin icon per image** = priors parsed (first check, before aligning).
- After Align, switch a viewport to **3Ds (Scene 3D View)** (view-aspect button, top-right of the view). You'll see camera frustums + a sparse cloud. Vendor docs: *"Each component contains camera poses and a sparse point cloud… you can move around the sparse point cloud and check the color poses."*
- **Component camera count:** the **1Ds view** shows how many inputs aligned in the component. For a correct locked import you expect all 422 cameras in one component at the exact metric positions you wrote.
- **Correct vs wrong, told quickly on a few images:**
  - **Correct:** frustums sit where the sensor physically was, all pointing *into* the scene/toward the LiDAR geometry; texturing later lands imagery on the right surfaces.
  - **Wrong – "cameras pointing outward"/mirrored/rotated 90–180°:** frustums face away from the scene, or the whole rig is rotated/flipped. This is an **axis-convention** problem (§3), not a position problem — positions usually look right while orientations are off. Fast test: pick 2–3 cameras with clearly distinct viewing directions and confirm each frustum's look-direction matches the actual photo content.
  - A practitioner converting external poses described exactly this: cameras positioned right but *"cam rotations are weirdly off… seems like a simple Y/Z axis swap."*

### 3. Rotation convention — real-world confirmation and the exact fix

**Confirmed facts (from an Epic-staff-endorsed, numerically-verified worked example):**
- `xcr:Rotation` = **world-to-camera** R, **row-major** (nine numbers, first three = first matrix row). RC staff (OndrejTrhan): *"the rotation is stored row wise."*
- Projection: `m = R·(Xw − C)`; internally `t = −R·C`; camera center `C = −Rᵀ·t`. This is the **same handedness as OpenCV/COLMAP's world-to-camera R** — so **do NOT transpose** your world-to-camera R when writing `xcr:Rotation`, and write the **camera center** (not COLMAP's `t`) into `xcr:Position`.

**The axis-flip question (the real gotcha):** RealityCapture's world coordinate system is right-handed, **Z-up** (Y-north, X-east). COLMAP's *camera-local* axes are X-right, **Y-down, Z-forward.** Because the two camera-local bases differ, a straight copy of an OpenCV/COLMAP R often yields "cameras pointing outward"/mirrored. The fix is a **change-of-basis (row permutation + sign flips) applied to R — not a transpose.** Concretely, left-multiply your camera-local rotation by a fixed signed-permutation matrix (e.g. flipping the Y and Z rows) so the camera's look/up/right axes are expressed in RC's convention. The one practitioner who solved this for an external (Cinema4D) source confirmed *"a simple Y/Z axis swap"* plus sign corrections was required; the exact final matrix is not published, so **you must determine your specific signed-permutation empirically** using the 2–3-frustum test (§2).

Because you already validated your exporter in a sandbox and it rendered correctly there, your axis mapping is very likely already right — but a sandbox RealityScan round-trip (RC→XMP→RC) is self-consistent and would not reveal a mismatch against a Point-LIO/OpenCV camera-axis convention. **Verify on real data with the 2–3-frustum test before trusting all 422.**

**Intrinsics you must get right (undistorted 1920×1200, pinhole):**
- `xcr:FocalLength35mm` = **(f_pixels ⁄ image_width_px) × 36** (referenced to a 36 mm sensor *width*). For 1920-wide images: `f35 = fx_px / 1920 × 36`. (Note: the internal *pixel*-projection scale RC uses is `max(width,height)`, but the 35 mm-equivalent focal is normalized by image **width × 36** — do not conflate the two.)
- `xcr:PrincipalPointU/V` = signed, normalized offset of the principal point from image center; **0 = centered.** Real RC XMPs show small values like `-0.0129 / 0.0017`. Confirm sign (U right, V down) and normalization match RC's convention — a flipped sign shifts texture projection.
- `xcr:Skew="0"`, `xcr:AspectRatio="1"` for square pixels (your case). Since PNGs are pre-undistorted, use a zero-coefficient distortion model. Tag spelling is RC's `xcr:DistortionCoeficients` under `xmlns:xcr="http://www.capturingreality.com/ns/xcr/1.1#"`, `xcr:Version="3"`.

### 4. Combining XMP-posed images + separate LiDAR cloud into ONE component

This is the make-or-break step.

- **Import the LiDAR as a laser scan (not as a "model").** Workflow/Import → LiDAR/point cloud. RealityScan converts your `.ply` to its internal `.lsp`. Choose **"Exact – use existing registration"** so the cloud keeps its metric coordinates and *defines the scene coordinate system.* Because your cloud has intensity and no RGB, set the LiDAR **"Features source" to Intensity** (default is Color) so any feature-based photo↔LiDAR registration can use the intensity channel.
- **Do they auto-co-register if they share coordinates?** Not blindly — alignment decides. Because both inputs are in the identical metric map frame and your cameras are locked, aligning should place them together. But RealityScan groups inputs into **components** based on successful cross-registration; if it can't find enough features tying images to the LiDAR, you get **two separate components** even when the numbers agree.
- **If you get two components, reliable fixes (in order):**
  1. **Control points (most reliable):** place ≥3 shared control points visible in both images and locatable on the LiDAR geometry, then Align again — RealityScan uses them to fuse components. Three points define origin + scale + orientation.
  2. **Rely on shared coordinates + priors:** since the cloud is Exact and cameras Locked in the same frame, they are geometrically coincident; ensure priors are enabled in Alignment Settings so RS honors the absolute coordinates.
  3. **Merge Components tool** (ALIGNMENT tab) — merges existing components without adding inputs.
- **Known behavior/perf gotchas here:** RealityScan 2.1 documentation lists *"Using LSP files in components significantly slows down alignment with images"* and *"Calibration or lens group is not accepted when importing images with corresponding XMP files"* — plan for slow alignment and don't rely on lens/calibration grouping via XMP.

### 5. Meshing from LiDAR geometry + texturing from images

Once images + LiDAR share one component:
1. **Set a reconstruction region** (the "box") to bound the LiDAR volume of interest. Auto-set it or import/edit an `.rsbox`.
2. **Calculate Model** (Mesh & Color / Reconstruction). RealityScan meshes from all geometric inputs; with a dense LiDAR cloud present, the mesh is driven by the LiDAR points. (2.1 supports class-selective meshing for classified LAS/LAZ — not your plain `.ply`.)
   - To keep geometry from LiDAR rather than image-based depth, keep the LiDAR as the geometry source in the component; RS uses LiDAR points directly for the surface. There is no single "use LiDAR not photos" checkbox — geometry source follows what's in the component and the reconstruction settings.
3. **Texture.** RealityScan projects the posed images onto the mesh: *"RC uses the images to project a texture on the 3D model."* Choose geometric or mosaic UV unwrapping (2.1 offers both) to tune texel density.
4. **Export** the UV-textured mesh (OBJ/FBX/USD) for Unreal; 2.1 can render from exact camera intrinsics/extrinsics for verification.

### 6. Known gotchas & failure modes (RealityScan 2.1 / 2.1.1)

- **⚠️ 2.1.1 XMP-orientation regression (named, current).** User "ryanwellence" reported on the Epic Developer Community Forums (April 1, 2026, thread "Camera Alignment incorrectly reading XMP Camera Priors in 2.1.1"): *"since this update from 2.1.0 to 2.1.1 I've noticed that all of the scans are consistently orientated wrongly."* (His side-by-side comparison was RS **2.0.1 vs 2.1.1**.) Epic staff Jakub Vanko replied April 7, 2026, *"There were changes made to the XMP exporter, but it shouldn't affect older scripts,"* and April 10, 2026, *"We plan to push a hotfix, probably next week."* **Pin your RealityScan build and test XMP orientation on the exact version you'll run on real hardware.**
- **FocalLength35mm normalization:** width×36, not max(w,h)×36 (§3). Wrong here scales the projection and misaligns texture.
- **Principal-point sign/normalization:** a flipped sign or wrong normalization dimension offsets texture projection.
- **`_common.xmp` shortcut:** one file named `_common.xmp` in the image folder applies shared XMP fields to every image — handy if all 422 share one intrinsic set; per-image files (yours) coexist/override.
- **Locked vs Draft/High alignment:** locked poses don't need high-accuracy matching to place cameras, but you still need enough features for image↔LiDAR fusion; use normal alignment.
- **Coordinate-system prompt on import:** for a local metric frame that is not geo-referenced, choose **Local** coordinates (set LiDAR "Georeferenced = No / Local") so RS doesn't treat metric map coordinates as a geographic CRS.
- **Metric scale:** both inputs are already metric and Exact/Locked — don't add scaling constraints that fight the data.

### 7. Alternatives if XMP + separate-LiDAR won't merge

Ranked by reliability for your exact situation (posed images + registered intensity-only cloud in one metric frame):

- **(a) Control points to force the merge — MOST reliable, lowest engineering.** Keep your XMP+LiDAR workflow; add ≥3 control points to bridge components. Vendor-blessed path for "two components that should be one."
- **(b) Mesh the LiDAR externally, import as a model, texture in RealityScan — very reliable, decouples the risky step.** Build the mesh from your `.ply` in CloudCompare/Open3D/etc., import into RealityScan as a **model for re-texturing**, bring in the XMP-posed images, and texture. This sidesteps RS's meshing/registration entirely and uses RS only for projection texturing — robust when geometry is already good.
- **(c) Colorize the LiDAR cloud from the images first, import as a colored cloud.** Project images onto the cloud (you have poses + intrinsics) for per-point RGB, then import the colored `.ply`. Gives RS a color channel for feature-based photo↔cloud registration and a colored mesh, but you lose RealityScan's high-res image-texturing quality.
- **(d) Populated-COLMAP (reproject LiDAR to synthesize POINTS2D observations).** You already ruled out pose-only COLMAP (RealityScan rejects empty-observation models — the "physical end of the tape" error). Reprojecting LiDAR points into images to create real 2D observations would make a COLMAP model RS accepts, but it's the most engineering-heavy and error-prone route. Use only if (a)/(b) fail.

**Recommendation:** attempt XMP + Exact-LiDAR + Align first; if two components appear, add control points (a). Keep (b) — external mesh + RS texturing — as the reliable fallback.

---

## Recommendations (staged)

**Stage 0 — Version lock & 10-image dry run.** Before real hardware: pick one RealityScan build (given the 2.1.1 XMP regression, validate your target version explicitly). Take ~10 images + XMPs + a cropped LiDAR tile, and run the whole pipeline. *Proceed when:* all 10 cameras show pin icons, land in one component with frustums pointing into the scene, and a quick texture lands imagery on the right surfaces.

**Stage 1 — Confirm orientation on real poses.** Import 10–20 real frames; do the 2–3-frustum look-direction test (§2). *If cameras point outward/mirrored:* apply/adjust the signed-permutation axis fix on R (§3) — do not transpose. Re-export those XMPs and retest until frustums are correct.

**Stage 2 — Full camera import + LiDAR merge.** Add all 422 with XMPs (Add Folder), verify pins, import `.ply` as laser scan with **Exact** registration and **Intensity** features, choose **Local** coordinates, Align. *Threshold:* one component containing all cameras + the cloud. *If two components:* add ≥3 control points and re-Align.

**Stage 3 — Mesh + texture.** Set reconstruction region → Calculate Model (LiDAR-driven) → Texture from images → export UV-textured mesh (FBX/USD/OBJ) for Unreal. *Quality check:* texture seams follow geometry; no ghosting that would indicate residual pose error.

**Fallback trigger:** if Stage 2 refuses to merge after control points, or meshing tries to use image depth and produces bad geometry, switch to **external LiDAR meshing + RealityScan re-texturing** (Alternative b).

---

## Caveats
- **Version sensitivity is real:** the 2.1.1 XMP-orientation issue is a live, Epic-acknowledged report with a promised hotfix; behavior may differ between 2.0.1, 2.1.0, 2.1.1, and any later hotfix. Treat exact GUI label positions as approximate — Epic reorganized ribbons in 2.1.
- **The exact COLMAP→RealityCapture axis-flip matrix is not officially published.** Confirmation that a Y/Z swap + sign flips is needed is from a practitioner; nail your specific signed-permutation empirically. Your sandbox validation likely used an RC→XMP→RC round-trip, which is self-consistent and would not reveal a mismatch against a Point-LIO/OpenCV camera-axis convention — hence the Stage-1 real-data check.
- **"One component if coordinates match" is not guaranteed.** RealityScan components form from successful cross-registration, not shared numbers alone; the control-point bridge is the dependable insurance.
- **Intensity-only cloud:** feature-based photo↔LiDAR registration is weaker without RGB; control points compensate.
- Some vendor pages (Epic Developer Community KB, incl. the "RealityCapture XMP Camera Math" article) are JavaScript-rendered and their exact prose could not be extracted verbatim; the XMP-math specifics here are corroborated from Epic-staff-endorsed forum worked examples and the RealityScan Help pages rather than the KB body itself.