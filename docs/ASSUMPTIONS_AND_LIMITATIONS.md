# Assumptions and limitations

**This is a mission-planning research prototype. It is not certified for astronaut EVA navigation or life-support decisions.**

## What is observed, derived, assumed, simulated, unknown

| Label | Items |
|---|---|
| NASA observation | CTX DTM elevations, CTX orthomosaic pixels, Perseverance localizations, Navcam raw images, MEDA sol 684 pressure and irradiance |
| Derived (this software) | slope, hillshade, route geometry, length, elevation gain and loss, geology fraction along a route, alignment statistics |
| Illustrative model (user inputs) | flat speed 40 m/min, ascent rate 10 m/min, maximum slope 15°, time budget 420 min, consumable 500 units at 1.0 units/min walking and 0.6 units/min at a stop, reserve 25 %, slope weight 3 |
| Simulated | the habitat, the crew, Operation Delta Return, science activity durations, blocked zones, consumable loss |
| Unknown | rocks, boulders and scarps under ~40 m, soil bearing strength, dust, lighting, real-time weather, suit performance, human physiology |

## Limitations

1. **Resolution.** 20 m posts and a 40 m slope baseline. A route that is "feasible" at this scale can still be blocked by a 1 m boulder field or a 3 m ledge. Slope is a macro-terrain indicator, not obstacle detection.
2. **Cell-centre geometry.** Routes are polylines through 20 m cell centres with 8 headings. The real walking distance is longer.
3. **Time and consumable model.** A Naismith-style rule with illustrative numbers. It is not calibrated to suited walking on Mars, and descent is assumed free.
4. **Geology alignment.** SIM 3464 has documented random 100-200 m offsets from this base map. The "units along route" numbers are regional context only.
5. **Optical/DEM alignment.** The products share grid and CRS. The image cross-correlation check is inconclusive because of illumination. Visual inspection shows the delta scarp, craters and slope features coinciding, but no sub-pixel registration was measured.
6. **Rover positions as science sites.** Coordinates are rover parking positions recorded during the campaigns. Targets lie metres away.
7. **MEDA.** One historical sol. Hourly means include every finite sample; quality-flag columns were not applied beyond dropping empty values. The PDS label lists the pressure-uncertainty unit as kelvin, which looks like a label error; the column was not used. This is not a forecast.
8. **Blocked zones are circles.** Real hazards would have other shapes. The zone is a planning abstraction.
9. **Single study area** (8.1 × 4.5 km), sized for interactive CPU planning. The grid size limit is enforced (`max_cells = 250,000`).
10. **No authentication or rate limiting.** The FastAPI server is meant for local use; add both before exposing it publicly. CORS is limited to the local dev origins. The public build is static (GitHub Pages) and runs the engine in each visitor's browser, so there is no public server to protect.
11. **Default-policy results.** On the default mission the terrain-aware route is 108 m longer outbound but has a lower maximum slope (12.5° vs 15.0°). This is one outcome under illustrative weights, not a general claim of improvement.
