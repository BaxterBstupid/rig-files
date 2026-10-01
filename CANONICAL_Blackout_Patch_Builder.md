---
name: blackout-patch
description: Canonical workflow for the user's Blackout Lighting Console rig. Use whenever the user sends a rental order, gear list or light list (PDF or text) to patch, asks to build/import a Blackout patch CSV, or asks how to assign/address Astera tubes (Titan, Helios, Hyperion) to patch slots with an ART7 box. Produces a Blackout-native patch CSV using exact seed strings, and walks through Astera DMX Configurator assignment.
---

# Blackout Patch — canonical workflow

Two recurring jobs:
- **A. Rental list to patch CSV**
- **B. Assigning Asteras to their patch slots**

## A. Rental list → Blackout patch CSV

**Output:** a CSV that imports via **Blackout → Patch → Import Patch** with no matching step.

**Header, exactly:**
`FIXTURE_NUMBER,ADDRESS,ADDRESS_FOR_LABELS,MANUFACTURER,FIXTURE_TYPE,DMX_FOOTPRINT,DESCRIPTION,MODE,LABEL,LABEL_COLOR`

**Field formats:**
- `ADDRESS` = `start-end` (end = start + footprint − 1)
- `ADDRESS_FOR_LABELS` = `U/AAA` (e.g. `1/033`)
- LF line endings, no trailing newline
- One hex label colour per fixture type

**Rules:**
1. **Seed strings only.** MANUFACTURER, FIXTURE_TYPE, DMX_FOOTPRINT, DESCRIPTION and MODE must be copied verbatim from `references/seed.csv`. Guessed names make Blackout substitute a different fixture (Vortex8 became a Nanlite, LiteMat 2L became an Arri S60) and fall back to reduced channels.
2. **Keep each type together:** sequential fixture numbers per type (Astera 1…8).
3. **Pack addresses back to back** by true footprint. No overlaps. Move to universe 2 after 512.
4. **Leave dimmers off the patch.**
5. **Preferred mode:** CCT/HSI, 8-bit where the seed has it. Otherwise use the seed's mode.
6. **DMX lights only.** Skip non-DMX HMIs, China balls, Variacs, squeezers, distro, grip and receiver kits.
7. **Kits count per unit.** An "8-Light Kit" is 8 fixtures.
8. **Unknown fixture type:** flag it and don't guess. The user patches one on the iPad, exports, and the row is added to `seed.csv`.
9. **Double-check against the source list** (counts, Gen 1 vs Gen 2 variants), then deliver:
   - the CSV
   - a summary table: fixture numbers, labels, profile, mode, channel count, addresses
   - the pending-confirmation rows
10. **Transfer:** PC to iPad/Mac with no AirDrop (USB-C stick in the UGREEN hub, email, or iCloud Drive). Never open and save the file in Excel, which turns `1-8` and `1/009` into dates.
11. **Import:** Patch → Unpatch (clear the old patch) → Import Patch. Check the fixture types, the Description/modes and that there are no overlaps.
12. **Put fixtures whose modes are uncertain last in the patch**, so fixing them on set doesn't shift other addresses.

## B. Assigning Asteras to patch slots (ART7)

**How it works:** Blackout doesn't discover lights, because DMX is one-way. Each patch slot is an address. The tube set to that address and mode *becomes* that fixture.

**Canonical method: Blackout DMX Configurator (needs the ART7 connected)**
1. Connect the ART7:
   - **In AsteraNext:** ART7 → Wi-Fi Settings: Access Point ON, Join Network OFF, then save and reboot.
   - **In Blackout:** Link Status → Connect to Astera → Add New Astera Box, then enter the PIN from the ART7 sticker.
2. **Pair** the tubes to the ART7 (Astera protocol): hold the power button on each tube until it blinks blue, then tap **Pair with Lights**.
3. **Link CRMX separately.** In List of Lights, select all → **Unlink CRMX**, then link to the transmitter. That's either the ART7's own node (Node Settings → Start Transmitter → Link with Lights) or the Aurora (Linking → Link).
4. **Patch the Asteras**, then tap the **Astera logo** in the Patch top bar to open the DMX Configurator. Address, mode and profile are auto-filled from the patch.
5. Tap **Send**, press **Enter on the tube**, tap **Next Fixture**, and repeat for every tube and every type.
   - **Shortcut:** Fixtures → Astera View State → select the tubes → **Assign to patch**.
6. **Identify tubes:** List of Lights → **Flash Fixtures**, in a chosen colour. Tape-number each tube to match its label.
7. **Test:** bring up each fixture in Blackout and confirm the matching tube lights.

**Remember:** pairing to the ART7 and CRMX linking are two separate steps. If the tubes pair but don't respond, CRMX isn't linked.
