# Five-minute Datathon demo

## 0:00–0:40 — Problem and LinuxONE

“Wildfire decisions fail when observations, exposure and response assumptions live in separate systems. CityShield puts a traceable historical replay, forecast evaluation and response sandbox on LinuxONE.” Show the page header, `/health` and the `s390x` deployment evidence. State that this is a research prototype.

## 0:40–1:25 — Establish the evidence boundary

Use **Paradise public data** and **Data status**. Point out the 2,017 FIRMS detections, 2017 ACS exposure, 2025 roads, coarse terrain and four blocked layers. Explain that FIRMS points are active-fire detections rather than a perimeter, and that NIST contributes verified time windows because its spatial symbols remain undigitized.

## 1:25–2:25 — Replay and predict

In **Camp Fire historical replay**, play the 14-frame timeline and switch between 2D and 3D. Stop at a FIRMS frame, choose a forecast lead and inspect one grid cell. State that the weather and fuel inputs are assumptions, the probability is uncalibrated and the model uses no observation after its issue time.

## 2:25–3:10 — Challenge the forecast

Open **Prediction versus subsequent observation**. Show the six short-lead windows and the persistence and radial baselines: precision 0.259, recall 0.703 and IoU 0.234 for the current model. Explain that the radial baseline has higher recall but more false alarms, and that the two long-lead windows are insufficient evidence. Do not describe FIRMS agreement as burned-area or life-safety accuracy.

## 3:10–4:25 — Test response assumptions

Open **Evacuation timing and response trade-offs**. Compare the assumed order times, then switch resource strategies. Point out that residents, reception areas and units are simulated; current results are neither historical evacuation outcomes nor GPS tracks. If clearance is incomplete, use **last successful arrival** and do not call it total clearance. Explain that early scenarios have no FIRMS-seeded hazard, so zero trapped people does not mean safe.

## 4:25–5:00 — Close with proof and next work

Show the model/data versions and audit identity. Finish with what runs today on LinuxONE and the next evidence needed for operational research: historical weather, digitized progression, 2018 roads and traffic, official evacuation records, fuel, water, facilities and independently calibrated incidents.

