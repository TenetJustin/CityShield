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

## Paradise evacuation and resource scenario

The response model uses the same frozen 500 m Paradise grid. It converts
aggregate ACS exposure into vehicle and walking demand, applies a seeded
lognormal departure delay, and moves vehicle platoons through a four-neighbour
road-cell graph with assumed capacity. Two off-grid reception areas are scenario
destinations. A forecast cell can block a route after its predicted arrival time.

The resource model ranks forecast cells either by predicted probability times
aggregate population exposure or by assumed travel time. Six simulated units are
assigned to unique cells. `protected_population` is probability × population ×
assumed effectiveness; it is not an observed rescue count or a validated benefit.

All scenarios carry a deterministic identity containing the order/issue time,
seed or strategy, hazard setting, model/data version and forecast identity.
Population totals are checked for conservation.

## Known limitations

- The Paradise grid is derived from public geography, population and coarse terrain, while fuel, weather and spread parameters remain assumed and uncalibrated.
- P10/P50/P90 values are ensemble state summaries, not calibrated probabilities.
- The model does not represent ember transport, crown-fire transition, suppression tactics, smoke chemistry or structure ignition.
- Route optimization is disabled until an authoritative road graph, closures and capacity assumptions are available.
- Satellite active-fire detections must not be displayed as exact fire-front geometry.
- No recommendation is an official warning, evacuation order, road closure or dispatch command.
- Evacuation behaviour, road capacity, reception areas, resource positions and effectiveness are assumed rather than observed.
- The response model has no historical traffic, order-compliance, shelter-intake, apparatus GPS or rescue-outcome validation.
- Fire suppression does not feed back into the spread forecast.
- A reported evacuation clearance time exists only when every modelled person reaches a reception area; otherwise the API reports an incomplete clearance and separately exposes the last successful arrival.

## Validation required after city selection

Freeze complete historical incidents by event, replay only records available at each decision time, and compare against persistence/simple spread baselines. Report perimeter overlap, arrival-time error, Brier/reliability, missed high-exposure cells, latency and decision stability. Never split overlapping windows from the same incident across train and test.

