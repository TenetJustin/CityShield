# Five-minute Datathon demo

## 0:00–0:40 — Problem and platform

“Wildfire decisions fail when hotspots, weather, roads and exposure arrive in separate systems. CityShield runs the complete Detect–Decide–Respond loop on LinuxONE and keeps every result traceable.” Show `/health`, platform readiness and the explicit synthetic-data badge.

## 0:40–1:40 — Detect streaming change

Click **Run live demonstration**. Point out each arriving observation and the immediate update in the 3D world state. Explain `valid_at` versus `available_at` and why this prevents hindsight leakage.

## 1:40–2:35 — Predict

Play the +30, +60 and +120 minute timeline. Rotate the scene and select a cell. Show the four risk bands, risk footprint and area-growth rate. State that the current ensemble is an uncalibrated transparent baseline; the area-growth rate is not physical fire-front speed.

## 2:35–3:25 — Decide with a paired scenario

Open **Test a scenario** and select **Dry gust** or **Wind turns**. Explain that baseline and scenario use the same evidence snapshot. The interface selects the cell with the largest change. Then open **Review action** to show prioritized advisory actions and the disabled route optimizer.

## 3:25–4:10 — Respond safely

Approve the recommendation for coordination. Emphasize that approval records a human decision but sends no public warning or dispatch command. Expand **Evidence & system details** to show the new audit entry and hash.

## 4:10–5:00 — Controlled RSI and LinuxONE

Run the demo RSI evaluation in **Evidence & system details**. Show the shadow candidate, diagnostic metrics and promotion gates. Finish with LinuxONE deployment evidence and the next step: replace the city package and spatial mapper.

