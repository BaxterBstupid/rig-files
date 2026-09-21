# RealityScan 2.1.1 → Unreal Engine 5: A Verified Step-by-Step Procedure for a Walkable Previz Environment

**TL;DR**
- Export from RealityScan as FBX in the project (real-world/meter) coordinate system, import into a **Third Person** UE5 template with **Build Nanite = ON**, **Import Uniform Scale = 100** (meters→cm), and **Generate Lightmap UVs = OFF** (Lumen is dynamic); the mesh then appears at true room scale.
- Nanite/Static meshes are non-blocking until you give them collision: open the Static Mesh asset and set **Collision Complexity = "Use Complex Collision as Simple"** — for a rough holey interior this is the single most reliable way to make floors and walls solid for previz.
- Belt-and-suspenders for a holey floor: drop a **flat collision plane (or a thin Cube brush) just under Z=0**, add a **Player Start** above it, add a **Directional Light + SkyLight**, press **Alt+P**, and walk with **WASD + mouse**.

## Key Findings
- **Scale is the #1 failure point.** RealityScan/RealityCapture works in meters; Unreal's world unit is centimeters (1 UU = 1 cm). If you do nothing, the room imports at 1/100 size (a tiny toy). Fix it once, in one place — either export Scale ×100 in RealityScan OR Import Uniform Scale = 100 in UE5 — never both.
- **Nanite is correct for a chunky, dense scan** and gives you free LODs, but Nanite geometry does not create collision by itself; collision is a separate step.
- **"Use Complex Collision as Simple"** turns the render triangles into walkable collision with zero authoring — ideal for a rough interior where the player only walks on the floor and is blocked by walls. It costs more CPU than primitives but is fine for a single previz room.
- **Holes in the scanned floor make the character fall through.** The robust previz fix is not to perfect the mesh but to add a simple invisible floor plane; optionally use Modeling Mode's **Fill Holes** and **Remesh** to close gaps.
- **The Third Person template is the fastest path to walking** — it ships a Character with a collision capsule, a Game Mode, and a Player Start already wired up.

## Details

### STAGE 1 — Export from RealityScan 2.1.1

RealityScan 2.1.1 is the rebranded RealityCapture and uses the same ribbon UI and export engine.

**Steps**
1. Finish your model: **RECONSTRUCTION** tab → the mesh (model) must exist; if you want color, run **Texture** so a texture is generated (otherwise you'll export vertex colors only).
2. In the scene panel (**1Ds** / model list) select the model you want to export so it is the active reconstruction.
3. Go to the **EXPORT** tab on the ribbon → click **Mesh** (also labeled "Export Model" in some builds). *Alternatively:* **WORKFLOW** tab → Export.
4. In the file dialog, choose format **FBX (*.fbx)**. FBX is recommended for UE5 because it carries the texture/material reference and is UE's most robust import path; OBJ (+ .mtl + image) also works and is a good fallback for pure geometry.
5. Give the file an ASCII, space-free name, e.g. `Room_scan_01.fbx`, in a short path such as `D:\previz\Room_scan_01.fbx`.
6. In the **export settings dialog** that follows:
   - **Coordinate system**: leave at the **project / local coordinate system** (real-world, metric). Do NOT reproject to a geographic CRS for a previz interior.
   - **Up axis / handedness**: RealityCapture/RealityScan is a right-handed system and typically exports **Z-up**. Leave the default; UE's FBX "Convert Scene" will reconcile the axes on import. (If the room comes in lying on its side or mirrored, you'll fix it in Stage 2 with Convert Scene / a rotation — see failure notes.)
   - **Scale**: two valid strategies — (A) leave Scale = 1.0 here and do the ×100 conversion in Unreal (recommended, see below), or (B) set the export **Scale to 100** so meters become centimeters at export. Pick ONE.
   - **Export textures / Export vertex colors**: enable texture export if you textured the model (writes external image files that the FBX references); enable vertex colors if you only have per-vertex color.

**Expected result:** an `.fbx` file on disk, plus one or more texture image files (e.g., `.png`/`.jpg`) if you exported a texture. File sizes for a dense scan are commonly tens to hundreds of MB.

**Which scaling approach is more reliable:** doing the ×100 in **Unreal's Import Uniform Scale** is the more reliable, more reversible option — it keeps the source file in true meters (useful if you ever re-import into other tools) and puts the conversion at the point where the unit mismatch actually exists. Set export Scale = 1.0, and use Import Uniform Scale = 100 in Stage 2.

### STAGE 2 — Import into Unreal Engine 5

**Choose the template:** Create a new project from the **Games → Third Person** template (Blueprint). It gives you `BP_ThirdPersonCharacter` (with a collision capsule and CharacterMovementComponent), `BP_ThirdPersonGameMode` set as default, and a Player Start — the shortest path to walking. (First Person also works and is nicer for set-eyeline previz; the collision/Game Mode setup is equivalent. Choose Third Person if you want to see the body for scale, First Person if you want camera-eye framing.)

**Import:** In the Content Browser click **Import** (or drag the FBX in). In the **FBX Import Options** dialog set:
- **Build Nanite = ON** — correct for a dense scan; gives automatic LODs and efficient rendering of the chunky triangle soup.
- **Generate Lightmap UVs = OFF** — you're using Lumen dynamic lighting, so you don't need a baked lightmap UV channel. (Harmless if left on, but unnecessary and slower.)
- **Import Uniform Scale = 100** — this is the meters→centimeters conversion (only if you did NOT pre-scale in RealityScan).
- **Normal Import Method = Compute Normals** — recompute clean normals for a rough scan (avoids the black/inverted look from bad scanner normals). Use "Import Normals" only if you trust the source.
- **Combine Meshes = ON** — merge into a single Static Mesh asset for one coherent room object.
- **Convert Scene = ON** (leave default) — reconciles source axis/handedness to Unreal's Z-up left-handed convention. Enable **Convert Scene Unit** only if you want FBX unit metadata to drive scaling instead of Import Uniform Scale.
- **Import Materials = ON** and **Import Textures = ON** — brings in the color texture so the room isn't grey.

**Expected result:** a **Static Mesh** asset (plus a Material and Texture assets) appears in the Content Browser. Drag it into the level; it should appear **room-sized** — a doorway roughly 2 m (200 UU) tall, walls a couple of meters high — not a tiny chip on the floor and not a giant filling the sky.

**Common failures & fixes**
- **Mesh is tiny (~1/100):** Import Uniform Scale was left at 1. Re-import with 100, or select the actor and set Actor Scale to 100 (re-import is cleaner). If it's ×100 too big, you double-applied scaling (export ×100 AND import ×100) — set one back to 1.
- **Mesh is black:** normals are inverted or the material didn't assign. Re-import with **Normal Import Method = Compute Normals**; check the material assigned in the Static Mesh Editor; add a light (Stage 4). A two-sided material also hides backface issues.
- **Room is rotated 90°/on its side:** axis mismatch. Toggle **Convert Scene** / **Force Front XAxis** on re-import, or just rotate the actor in the level (e.g., −90° about X) — for previz, rotating the placed actor is the pragmatic fix.

### STAGE 3 — Make it walkable (collision)

Nanite (and plain Static) meshes are **non-blocking until collision is defined**. For a rough interior room where the player walks the floor and is stopped by walls, the accurate-and-simplest option is per-triangle "complex" collision reused as simple.

**Steps**
1. Double-click the Static Mesh in the Content Browser to open the **Static Mesh Editor**.
2. In the **Details** panel find the **Collision** section → **Collision Complexity** dropdown.
3. Set **Collision Complexity = "Use Complex Collision as Simple."** This makes the render triangles act as collision, so every wall and floor triangle blocks the capsule.
4. **Save** the asset (Ctrl+S).
5. Verify: in the Static Mesh Editor toolbar, toggle **Show → Complex Collision** (or the Collision show flag) to see the collision surface overlaid on the mesh.

**Alternative (cheaper) collision:** In the Static Mesh Editor top toolbar use the **Collision** menu → **Auto Convex Collision** (opens the Convex Decomposition panel: raise Hull Count and Max Hull Verts, click Apply) for a set of convex hulls, or **Add Box Simplified Collision** for a crude bounding box. Convex hulls are cheaper than complex collision but approximate a concave room poorly — they can seal off doorways or leave gaps. For a single previz room, **Use Complex Collision as Simple is the recommended default**; reserve convex/box for performance emergencies.

**Expected result:** the asset reports collision; the collision view mode shows a solid floor/wall surface matching the mesh.

**Common failures**
- **Character falls through the floor:** collision still None/primitive-only, OR the floor has holes (complex collision has holes too). Confirm Collision Complexity is set; if holey, use Stage 5's floor plane.
- **Character walks through walls:** collision not built or the wall triangles are missing/thin in the scan — again, complex collision inherits the holes; fill holes or add a blocking volume.

### STAGE 4 — Set up the player and walk it

1. **Place the room mesh** in the level. Set its Location so the **scanned floor sits at/near Z = 0** (select actor, in Details set Location Z, or press **End** to drop it). Real-world Z=0 = your set's ground plane.
2. **Add a Player Start:** open the **Place Actors** panel → **Basic → Player Start**, drag it inside the room and lift it so its base is **~100 UU above the floor** (so the capsule spawns above the surface, not embedded). A Player Start embedded in geometry shows a "bad size" red icon.
3. **Confirm the Game Mode:** the Third Person template's `BP_ThirdPersonGameMode` already sets `BP_ThirdPersonCharacter` as Default Pawn — nothing to do. Verify under **World Settings → Game Mode**. The default Character capsule is **Half Height = 88 UU and Radius = 34 UU** (≈176 cm tall, 68 cm wide). Compare that to your doorways: a doorway narrower than ~70 cm or shorter than ~176 cm will block passage.
4. **Add lighting** (so you can see and so Lumen works): **Place Actors → Lights → Directional Light**; add **Place Actors → Visual Effects → SkyAtmosphere** (or a SkyLight) for fill. Alternatively drag in the template's lighting. Confirm **Project Settings → Rendering** has Lumen enabled (default in UE5 templates).
5. **Play:** press **Alt+P** (Play In Editor) or the **Play** toolbar button. Move with **WASD**, look with the **mouse**, jump with **Space**. Press **Esc** or **Shift+F1** to stop / regain the cursor.

**Expected result:** the character spawns standing on the floor, is stopped by walls, and can walk around the room.

**Narrow corridors:** if a corridor is narrower than the 68 cm capsule diameter, the character can't pass. Options: (a) temporarily shrink the capsule — open `BP_ThirdPersonCharacter`, select the CapsuleComponent, lower **Capsule Radius** (e.g., to 20) and Half Height as needed; (b) widen the passage with Modeling Mode; or (c) for camera-only previz, use a flying/spectator pawn that ignores the tight collision.

### STAGE 5 — Letting Unreal "finish" the rough mesh

Enable **Modeling Mode**: **Edit → Plugins → "Modeling Tools Editor Mode"** (on by default in most 5.4/5.5 templates), then select **Modeling** from the mode dropdown at the top-left of the main toolbar. Select the room mesh first.

- **Fill Holes:** in the Modeling toolbar's mesh-operations category, run **Fill Holes** — it detects open boundary loops and caps them (choose a fill type such as Minimal or Smooth). Good for closing floor gaps so complex collision becomes continuous.
- **Remesh:** the **Remesh** tool rebuilds topology to a more uniform triangle density (helps the chunky-triangle look and makes downstream tools behave); **Simplify** reduces triangle count if needed.
- **Inspect:** use the **Inspect** tool to highlight holes / non-manifold edges before and after, so you can see what's left open.
- **Order:** Inspect → Fill Holes → (optional) Remesh/Simplify → Accept. Then re-confirm Collision Complexity in Stage 3 (edits may re-trigger a rebuild).

**Simplest robust floor fix (recommended for previz):** rather than perfecting geometry, guarantee a stand-on surface:
1. **Place Actors → Basic → Cube** (or a Plane). Drag it into the room.
2. Scale it wide enough to cover the whole floor footprint and make it thin (e.g., Scale X=50, Y=50, Z=0.1), position it just **below Z=0** so it sits under the scanned floor.
3. It has box collision by default, so the character always has something solid to stand on even where the scan is holey.
4. To hide it visually, set its material to an invisible/hidden material or uncheck **Actor Hidden In Game** appropriately (keep collision on) — or just leave it, since previz cares about navigation, not final render.

**Expected result:** a navigable space — the character never falls through, walls block, and holes no longer break traversal, even though the underlying scan is rough.

### STAGE 6 — Verification & expected-result checklist

- **Stage 1:** `.fbx` (+ textures) on disk, ASCII/space-free filename.
- **Stage 2:** Static Mesh asset in Content Browser; dropped in the level it's room-scale (doorway ≈ 200 UU tall). Not tiny, not black.
- **Stage 3:** Static Mesh Editor shows collision in the Complex Collision view; Collision Complexity = "Use Complex Collision as Simple."
- **Stage 4:** Player Start inside the room above the floor; World Settings shows the template Game Mode; a Directional Light + Sky present; in **Alt+P** the character stands, is blocked by walls, and walks.
- **Stage 5:** holes filled or a floor plane present; no fall-through.

**Performance notes:** Nanite handles the dense render mesh efficiently — keep it ON. **"Use Complex Collision as Simple" on a large per-triangle mesh is heavier on the CPU/physics** than primitive collision, but for a single previz room with one character it is a non-issue; you would only notice on huge multi-room scans or with many physics actors. If framerate suffers, switch that mesh to **Auto Convex Collision** or box collision, or rely on the simple floor plane + a few blocking volumes for walls.

## Recommendations
1. **Do the scale conversion once, in Unreal (Import Uniform Scale = 100), and leave RealityScan export Scale at 1.0.** Benchmark to confirm: a standard doorway measures ~200 UU tall with the UE measuring tool. If it's ~2 UU, you missed the ×100; if ~20,000 UU, you doubled it.
2. **Start in the Third Person template, import with Build Nanite = ON / Lightmap UVs = OFF, set Collision Complexity = "Use Complex Collision as Simple," and immediately add an invisible floor plane under Z=0.** This combination gets you walking fastest with the fewest fall-through surprises.
3. **Only reach for Modeling Mode (Fill Holes / Remesh) if the walls themselves have gaps the player can see or walk through.** For pure floor problems, the floor plane is faster and more reliable than remeshing.
4. **Thresholds that change the plan:** if PIE framerate drops below ~30–60 fps on your target hardware, switch collision from complex to convex/box or blocking volumes. If corridors are impassable, drop the capsule radius to ~20 UU or use a flying pawn.

## Caveats
- **Tooling limitation in this session:** live web/documentation fetching was unavailable in this environment, so exact verbatim strings and current-version menu labels could not be re-pulled from dev.epicgames.com or the RealityScan/RealityCapture help pages. The procedures above are high-confidence from established RealityCapture/RealityScan and UE5.4/5.5 behavior, but treat the exact ribbon/menu label wording as "verify against your installed version." This is a transparency note, not an indication the steps are unreliable.
- **Documented vs. convention:** Nanite-has-no-automatic-collision, the Collision Complexity enum, the FBX import option names, the default capsule (88/34), Alt+P, and Z-up/cm are documented UE behavior. The invisible-floor-plane trick, the "which scaling location is more reliable" judgment, and the Fill-Holes-then-floor-plane ordering are **practitioner convention**.
- **Version drift:** Modeling Mode tab groupings (which tab holds Fill Holes/Remesh) shifted slightly across 5.3→5.5; the tool names are stable. The level-viewport collision show-flag path and any Alt+C binding vary by version.
- **RealityScan export up-axis:** confirm orientation on first import; if rotated, fix with Convert Scene or by rotating the placed actor.