# Model card

## Intended use

CityShield demonstrates how streaming observations can update a city-scale wildfire belief state and support time-critical, human-reviewed decisions on LinuxONE. The current transparent ensemble is a software integration baseline, not a validated operational spread model.

## Inputs

- active-fire or perimeter evidence;
- wind speed/direction, humidity and temperature;
- cell fuel, slope, population and critical-facility attributes;
- optional road closure and response-resource states.

## Outputs

- P10/P50/P90 state proxies at 30, 60 and 120 minutes;
- paired scenario differences;
- prioritized advisory actions with reasons and safety notes;
- post-event Brier score, log loss, precision and recall for controlled RSI diagnosis.

## Current method

A grid graph propagates neighbor pressure using fuel, remaining fuel, terrain, dryness, temperature, wind strength and directional alignment. Twenty-four deterministic-seed ensemble members perturb weather and spread rate. Identical evidence, configuration and scenario inputs reproduce the same run ID and values.

## Known limitations

- Synthetic cells and uncalibrated parameters are used until a city is selected.
- P10/P50/P90 values are ensemble state summaries, not calibrated probabilities.
- The model does not represent ember transport, crown-fire transition, suppression tactics, smoke chemistry or structure ignition.
- Route optimization is disabled until an authoritative road graph, closures and capacity assumptions are available.
- Satellite active-fire detections must not be displayed as exact fire-front geometry.
- No recommendation is an official warning, evacuation order, road closure or dispatch command.

## Validation required after city selection

Freeze complete historical incidents by event, replay only records available at each decision time, and compare against persistence/simple spread baselines. Report perimeter overlap, arrival-time error, Brier/reliability, missed high-exposure cells, latency and decision stability. Never split overlapping windows from the same incident across train and test.

