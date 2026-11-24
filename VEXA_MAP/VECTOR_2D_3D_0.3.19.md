# VEXA MAP 0.3.19 — 2D passenger, 2D/3D driver, vector PBF and road engine boundary

## What is implemented in source

- **VEXA Client:** fixed **top-down, north-up, 0° pitch / 0° bearing** camera on route and location changes; tilt and rotation gestures disabled; MapLibre max pitch 0°. The passenger does not have a 3D control.
- **VEXA Driver:** independent saved setting **2D / 3D** and a follow-car toggle. In 2D the camera is north-up with 0° pitch. In 3D the camera uses ~55° pitch and the available GPS bearing. Building extrusions appear **only if** a vector package includes a `building` source-layer. A raster map tilts in 3D but has **no volumetric buildings**.
- **Offline Android:** PBF and raster MBTiles from the existing verified download manager can be used by the MapLibre screen. A read-only loopback adapter serves XYZ tile requests from TMS SQLite rows. Gzipped PBF bytes include `Content-Encoding: gzip`. All street-label glyph requests are local. No remote fonts or tile URLs appear in offline vector styles.
- **Online VEXA MAP Server:** a vector style and PBF tiles work with a compatible vector MBTiles. `style.json?view=3d` includes building extrusions; the default style stays flat. Embedded glyphs are served over `/glyphs/{fontstack}/{range}.pbf`.
- **Road engine:** the existing server-side **OSRM** integration now requests `steps=true` and returns validated structured maneuvers (`type`, `modifier`, street name and coordinate), ready for a later GPS-matched instruction UI. **Do not interpret this as turn-by-turn navigation already working.**

## Required MBTiles contract

Produce an MBTiles SQLite file named `<region>.mbtiles` with:

- `metadata.format = pbf`, zoom bounds and optional center/bounds;
- `metadata.json` as TileJSON metadata including `vector_layers` with at least `transportation` **or** `road`; optional layers `transportation_name`, `place`, `water`, `landuse`, `landcover`, `building`;
- `tiles` table/view, tile coordinates TMS and tile_data PBF (raw or gzip). Vector layers should use compatible OpenMapTiles-style field names; street labels expect `name:ru` or `name`;
- optional table `vexa_glyphs(fontstack TEXT, range_start INTEGER, pbf BLOB)` with MapLibre glyph range files, e.g. `Noto Sans Regular`, ranges 0-255, 256-511, 1024-1279 (Latin/Cyrillic coverage). Labels are **disabled** when these three ranges are not complete. Other scripts need additional ranges. No typefaces are bundled by VEXA.
- optionally, the previously defined VEXA v1 `vexa_places`, `vexa_terms`, `vexa_nodes`, `vexa_edges` tables, for **limited** offline search and routing, prepared by `prepare_offline_navigation.py`.

### Operator preparation example

```bash
python VEXA_MAP/tools/prepare_vector_mbtiles.py \
  --mbtiles /data/central.mbtiles \
  --region central \
  --glyphs-dir /licensed-glyphs
```

`/licensed-glyphs/Noto Sans Regular/` must already contain **licensed, pre-generated** MapLibre glyph ranges such as `0-255.pbf`, `256-511.pbf`, `1024-1279.pbf`. The script imports bytes; it **does not** download fonts, create maps or generate glyph ranges. Do not distribute font or imagery assets unless their licence permits the planned use. Include map attribution and verify geodata licence terms (for OpenStreetMap, ODbL obligations may apply).

After modifying the MBTiles, **regenerate the package SHA-256 and publish the server manifest**, otherwise the mobile verification will reject the changed content. The current packaging tool is `VEXA_MAP/server/offline_packages.py`. Never edit an already-installed package in place on the phone: use the verified download flow to publish a new version.

## Current limitations, not yet production ready

- No real vector/imagery/road/font data for Russia is included in the source ZIP. Without valid packs the map remains a graphite placeholder.
- Android APK compilation, MapLibre GPU rendering, background/foreground behaviour, GPS heading quality, glyph rendering on an actual phone and offline device tests are **not yet verified**.
- Offline SQLite route finding is a **bounded prototype** (90 km), without turn restrictions, lane restrictions, traffic, U-turn policy, ferries, countrywide graph stitching or voice guidance. Its route length is a preview only and **never calculates a fare**.
- Server-side OSRM is a genuine routing engine only **when its licensed regional road dataset has been prepared and an OSRM service is configured**. Otherwise the API correctly returns an unavailable status.
- Driver 3D currently means **perspective map view + optional building extrusions**. Real 3D terrain, satellite imagery, tunnel/bridge semantics, turn instructions and inertial camera animation are separate tasks.
- When vector packs from several districts have incompatible layer schemas the online VEXA MAP Server refuses that set; the mobile offline renderer selects one district. A future unified map style and cross-district routing will need standardized builds.

## Follow-up for full road engine (not implemented in 0.3.19)

1. Prepare OSM-based car routing graphs for every district using a **consistent graph schema**, crossing boundaries with border-node stitching; develop reproducible Windows preparation steps under the agreed **250 GB local disk budget**.
2. Use native on-device graph query for offline navigation (or an embedded routing backend with suitable licence/runtime resources): restrictions on turns, one-way streets, speeds, vehicle limits, access tags, ferries, local restrictions and route alternatives. Separate graph storage from tiles when size/performance requires it; retain one signed regional-package manifest.
3. Add GPS map-matching, off-route detection, incremental rerouting, voice instructions, ETA recalculation and navigation accessibility. Show road closure / traffic only while online with appropriate sourced data.
4. Add multi-district handover, cross-country rules, internationalization, benchmarks (startup, RAM, route latency, disk), corruption/recovery tests and full tests on low-memory Android devices.
5. Client stays **always flat**. Driver 3D additionally gets true 3D terrain/bridges only after licensed elevation data and optimized terrain assets are provided.

## Test guide

```bash
cd VEXA-deploy
PYTHONPATH=VEXA_MAP/server python -m unittest discover -s VEXA_MAP/tests -p 'test*.py'
PYTHONPATH=. python -m unittest discover -s tests -p 'test*.py'
```

Live test: publish a **small licensed PBF district fixture** with matching metadata and glyph ranges, build Client + Driver APK in Android Studio, download and SHA-256 verify, enable airplane mode, check street labels. Verify Client has no tilt gesture; Driver switch 2D/3D works with GPS and the ``building`` layer is only extruded in Driver.
