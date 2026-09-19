# Road-time cache

`osrm_pairs.json` holds driving minutes and kilometres between villa and hub coordinates, fetched from the public
OSRM demo server (`router.project-osrm.org`, car profile) in September 2026. It is a snapshot: real road times change.
Keys are `lat,lon|lat,lon` (origin|destination, rounded to 5 decimals); values are `[minutes, km]`.
Only real OSRM answers are stored here; haversine fallbacks are never cached.

Road data © OpenStreetMap contributors (ODbL), https://www.openstreetmap.org/copyright
