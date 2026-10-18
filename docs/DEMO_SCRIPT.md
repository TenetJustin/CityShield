# Five-minute Datathon demo

## 0:00–1:00 — Live critical-decision loop and LinuxONE

“When new fire and weather data arrive, CityShield detects abnormal escalation, predicts which populated areas may be threatened next, and recommends time-sensitive actions with human oversight.” Run **Live update**. Follow FIRMS + NOAA through the Paradise grid, 30/60/120-minute outlook and decision queue. Show the source timestamp, inference latency, Git commit and `s390x` runtime evidence. If the result abstains because Paradise has no mapped detections, explain that this is required safety behavior rather than a failed demo.

Begin on the landing page. Read the current recommendation first, point to the
live Paradise map, then use **Get started** to enter the evidence and decision
workflow. **Preview 2018 spread** is explicitly historical and must not be
described as a current Paradise incident.

## 1:00–1:40 — Establish the evidence boundary

Use **Paradise public data** and **Data status**. Point out the 2,017 FIRMS detections, 2017 ACS exposure, 2025 roads, coarse terrain and four blocked layers. Explain that FIRMS points are active-fire detections rather than a perimeter, and that NIST contributes verified time windows because its spatial symbols remain undigitized.

## 1:40–2:35 — Replay and predict

In **Camp Fire historical replay**, play the 14-frame timeline and switch between 2D and 3D. Stop at a FIRMS frame, choose a forecast lead and inspect one grid cell. State that the weather and fuel inputs are assumptions, the probability is uncalibrated and the model uses no observation after its issue time.

## 2:35–3:20 — Challenge the forecast

Open **Prediction versus subsequent observation**. Show the six short-lead windows and the persistence and radial baselines: precision 0.259, recall 0.703 and IoU 0.234 for the current model. Explain that the radial baseline has higher recall but more false alarms, and that the two long-lead windows are insufficient evidence. Do not describe FIRMS agreement as burned-area or life-safety accuracy.

## 3:20–4:25 — Test response assumptions

Open **Evacuation timing and response trade-offs**. Compare the assumed order times, then switch resource strategies. Point out that residents, reception areas and units are simulated; current results are neither historical evacuation outcomes nor GPS tracks. If clearance is incomplete, use **last successful arrival** and do not call it total clearance. Explain that early scenarios have no FIRMS-seeded hazard, so zero trapped people does not mean safe.

## 4:25–5:00 — Close with proof and next work

Show the model/data versions and audit identity. Finish with what runs today on LinuxONE and the next evidence needed for operational research: historical weather, digitized progression, 2018 roads and traffic, official evacuation records, fuel, water, facilities and independently calibrated incidents.

