import { createContext, useContext, useRef, useLayoutEffect } from "react";
import FireShieldMark from "./brand/FireShieldMark.jsx";

export const MODULES = [
  {
    id: "live",
    title: "Live decision",
    en: "LIVE DECISION",
    detail: "Inputs · Risk · Review queue",
  },
  {
    id: "map",
    title: "Current observations",
    en: "CURRENT OBSERVATIONS",
    detail: "Town map · Terrain · Public data",
  },
  {
    id: "quality",
    title: "Data quality",
    en: "DATA QUALITY",
    detail: "Coverage · Checks · Missing inputs",
  },
  {
    id: "replay",
    title: "Replay & simulation",
    en: "REPLAY & SIMULATION",
    detail: "Replay · Evaluation · Response",
  },
  {
    id: "legacy",
    title: "Legacy exercise",
    en: "LEGACY EXERCISE",
    detail: "Synthetic 3×3 · Original workflow",
  },
  {
    id: "evidence",
    title: "System evidence",
    en: "SYSTEM EVIDENCE",
    detail: "Sources · Audit · Operating prerequisites",
  },
];
export function ConsoleHeader({ docsOpen, onWorkspace, onDocs }) {
  return (
    <header className="consoleHeader">
      <div className="consoleBrand">
        <FireShieldMark />
        <a href="/" aria-label="CityShield home">
          <strong>CityShield</strong>
          <small>WILDFIRE DECISION STUDIO</small>
        </a>
      </div>
      <nav aria-label="Main navigation">
        <button className={!docsOpen ? "active" : ""} onClick={onWorkspace}>
          Workspace
        </button>
        <button className={docsOpen ? "active" : ""} onClick={onDocs}>
          Product guide
        </button>
      </nav>
      <span className="previewMark">
        <i /> RESEARCH PROTOTYPE
      </span>
      <a className="homeLink" href="/">
        Home ↗
      </a>
    </header>
  );
}
export function ModuleRail({ active, onSelect }) {
  return (
    <aside className="moduleRail">
      <div className="railLocation">
        <span>PARADISE, CA</span>
        <small>500 m shared grid</small>
      </div>
      <nav aria-label="Workspace modules">
        {MODULES.map((m, i) => (
          <button
            key={m.id}
            className={active === m.id ? "active" : ""}
            aria-current={active === m.id ? "page" : undefined}
            onClick={() => onSelect(m.id)}
          >
            <b>{String(i + 1).padStart(2, "0")}</b>
            <div>
              <strong>{m.title}</strong>
              <small>{m.en}</small>
            </div>
            <span>↗</span>
          </button>
        ))}
      </nav>
      <div className="railBottom">
        <span className="railCross">＋</span>
        <p>
          OBSERVE.
          <br />
          REPLAY.
          <br />
          EVALUATE.
        </p>
        <small>
          RESEARCH PROTOTYPE
          <br />
          ADVISORY ONLY
        </small>
      </div>
    </aside>
  );
}
const chapters = [
  {
    id: "overview",
    title: "Product overview",
    en: "OVERVIEW",
    intro:
      "One entry point, two ways to explore. Use the workspace to inspect and interact; use this guide to understand methods and limitations.",
    blocks: [
      [
        "Workflow",
        "The homepage switches between the current map and a preview of the 2018 spread. Inside the workspace, use the six modules in the left navigation to explore each task. Open the product guide from the top navigation. Replay & simulation includes historical replay, model evaluation and response simulation.",
      ],
      [
        "Audience and scope",
        "Designed for project demonstrations, historical incident research and discussion of model results. Current public data, historical observations, predictions and synthetic exercises are labelled separately. The system provides research advice; it does not automatically issue alerts, order evacuations or dispatch resources.",
      ],
      [
        "Reading the interface",
        "Maps occupy the main viewing area, with parameters and layers nearby and results in compact cards. Detailed explanations live in this guide. Result timestamps, units, simulation labels, missing data, insufficient samples and unavailable forecasts remain visible in the workspace.",
      ],
    ],
  },
  {
    id: "live",
    title: "Live decision",
    en: "LIVE DECISION",
    intro:
      "From current observations to a risk outlook and a human review queue.",
    blocks: [
      [
        "Controls",
        "Select Run live update to request an update. Review FIRMS and NOAA input status, observations mapped to the grid, 30-, 60- and 120-minute risk outlooks, and the recommendation queue. Run evidence includes the model version, run identifier and timestamp.",
      ],
      [
        "When observations are absent",
        "The model may abstain when no FIRMS observations map to the grid. Empty values, abstained and no forecast do not mean zero risk. An absence of satellite detections does not prove an absence of fire.",
      ],
      [
        "Status and provenance",
        "Read each result alongside its source snapshot, model and run identity. LinuxONE run evidence identifies where computation took place; it does not establish independent validation of the forecast.",
      ],
    ],
  },
  {
    id: "map",
    title: "Current observations",
    en: "CURRENT OBSERVATIONS",
    intro: "Explore the town map, terrain and current public data.",
    blocks: [
      [
        "Views and refresh",
        "Switch between 2D town map and 3D terrain. Show 2018 boundary toggles the final historical boundary and returns to the 2D view. Refresh sources queries the sources again; a failed request displays an error while retaining the last successful snapshot.",
      ],
      [
        "Data sources",
        "Roads and town boundaries use Census 2025 geography. The terrain display uses 49 USGS 3DEP elevation samples, with vertical exaggeration for visibility. Weather comes from NOAA, incident records from NIFC and hotspots from NASA FIRMS.",
      ],
      [
        "Historical boundaries and current data",
        "The final 2018 boundary describes the event outcome, not its progression through time. Its date differs from current weather and incident observations. Satellite hotspots are detection points, not a burned perimeter. Source update times remain visible beside the results.",
      ],
    ],
  },
  {
    id: "quality",
    title: "Data quality",
    en: "DATA QUALITY",
    intro:
      "Distinguish observations, derived results, assumptions and missing inputs.",
    blocks: [
      [
        "Reviewing checks",
        "The summary covers the shared grid, FIRMS, ACS population and NIST time windows. Priority issues appear first. Show all checks expands the complete list with status, explanations and data version.",
      ],
      [
        "Spatial and temporal limits",
        "The FIRMS query area and shared grid do not fully overlap; detections outside the grid are counted separately. Historical observations include long gaps. Interpolation is an estimate, not a new observation. NIST map symbols have not been digitized, so only verified time windows provide temporal constraints.",
      ],
      [
        "Population and missing layers",
        "ACS population is an aggregate estimate allocated to grid cells by area, not the real-time location of residents. Default fuel values are assumptions. Water and facility layers without authoritative data are marked missing; invented locations are not substituted.",
      ],
    ],
  },
  {
    id: "replay",
    title: "Historical replay & forecast",
    en: "HISTORICAL REPLAY",
    intro:
      "Compare observations, predictions and the next observation on a shared grid.",
    blocks: [
      [
        "Replay controls",
        "Choose a time with play/pause, 0.5× / 1× / 2× / 4× speed, previous/next observation, the slider or snapshot buttons. NIST time windows and FIRMS snapshots use distinct labels. Layers and detail panels follow the selected time.",
      ],
      [
        "Maps and cells",
        "Switch between 2D, 3D or Both. Independently toggle predictions, observed cells, new hotspots, roads and population bars. Select a cell on the map or in the dropdown to inspect population, elevation, roads, predictions and missing layers. The 3D height combines coarse elevation and risk as a viewing aid; it does not represent flame height or a fire-behaviour model.",
      ],
      [
        "Forecast lead and scenarios",
        "Choose the next-observation interval or +30 / +60 / +120 minutes. Baseline, wind-shift and suppression assumptions remain available. Forecasts use only information available at issue time. Without mapped observations, the model does not invent a fire. Scenario forecasts are distinct from baseline evaluation.",
      ],
    ],
  },
  {
    id: "evaluation",
    title: "Model evaluation",
    en: "MODEL EVALUATION",
    intro: "Measure agreement with subsequent FIRMS detections.",
    blocks: [
      [
        "Evaluation protocol",
        "Issue a forecast at t0 using observations available by t0, then evaluate cells first detected in (t0, t1]. NIST provides temporal constraints only; undigitized spatial symbols are not scored.",
      ],
      [
        "Key metrics",
        "Precision is the share of predicted cells detected later. Recall is the share of newly observed cells covered by the prediction. IoU is the intersection divided by the union of predicted and observed cells. Additional results include arrival-time error, population-exposure error, miss distance and radial/persistence baselines.",
      ],
      [
        "Sample size and interpretation",
        "Results are grouped by forecast lead. Headline metrics are withheld below the configured reporting floor; raw metrics can be expanded. Correlated windows from a single incident do not constitute independent validation. These metrics do not measure real-world life safety or rescue performance.",
      ],
    ],
  },
  {
    id: "response",
    title: "Response simulation",
    en: "RESPONSE SIMULATION",
    intro:
      "Explore evacuation timing, corridors and firefighting resources through explicitly labelled simulations.",
    blocks: [
      [
        "Evacuation timing",
        "Choose early, middle or late order scenarios and toggle predicted fire hazard. Compare people who left beforehand, evacuated, trapped or unaccommodated, together with clearance and congestion. Inspect the selected curves and reception-area capacity. When an early scenario has no mapped hazard forecast, zero trapped people does not imply safety.",
      ],
      [
        "Evacuation corridors",
        "The map shows modelled population flows, unaccommodated origins, reception exits and simulated resource connections. Routes are scenario calculations on the shared grid, not observed GPS tracks.",
      ],
      [
        "Firefighting resources",
        "Switch between Exposure-weighted, Nearest-first and No action baseline. Inspect unit targets, travel, arrival and task-end times, protected exposure and missing-water warnings. Resource strategies have separate simulation calculations and do not describe units actually deployed.",
      ],
      [
        "Formulas and parameters",
        "Expand Simulation assumptions, Resource assumptions and formulas, or Model formulas, parameters and limits in the workspace to inspect assumptions associated with the current results. Residents are synthesized from aggregate ACS population; vehicles, reception areas and firefighting units are scenario assumptions.",
      ],
    ],
  },
  {
    id: "legacy",
    title: "Legacy exercise",
    en: "LEGACY EXERCISE",
    intro: "Access the original synthetic 3×3 workflow in its own module.",
    blocks: [
      [
        "Original workflow",
        "Legacy live / Legacy replay, synthetic-stream and replay controls remain available, together with Understand risk → Test a scenario → Review action. Use 2D / 3D / Both views, layers, the timeline, cell selection and scenario comparison.",
      ],
      [
        "Human review",
        "Approve and reject controls appear when the original prerequisites are met. Approval records a coordination decision; it does not issue public alerts, order evacuations or dispatch responders. Legacy exercise data is synthetic and must not be presented as a historical result.",
      ],
    ],
  },
  {
    id: "evidence",
    title: "System evidence",
    en: "SYSTEM EVIDENCE",
    intro:
      "Understand system status through sources, operating prerequisites and audit records.",
    blocks: [
      [
        "Evidence available",
        "Inspect source-adapter status, delivery gates, audit-chain verification, processed-observation counts, evidence snapshots and forecast-run identifiers. An implemented adapter does not mean a city is ready for live operation.",
      ],
      [
        "Controlled improvement",
        "Run demo evaluation keeps its original prerequisites and evaluates a candidate after a forecast is completed. Shadow candidates do not automatically replace the active model.",
      ],
      [
        "Interface and operating scope",
        "The workspace separates observation, replay, evaluation and simulation tasks. Use source timestamps, data-quality checks and run evidence to understand each result before interpreting it. This research interface does not issue operational instructions.",
      ],
    ],
  },
];
// Links also work when opened in a new tab or loaded directly.
export const GuideNavigation = createContext(null);
const sectionId = (title) =>
  title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
export function guideTarget(chapter = "overview", section = "") {
  const current = chapters.find((item) => item.id === chapter) || chapters[0];
  return {
    chapter: current.id,
    section: current.blocks.some(([title]) => sectionId(title) === section)
      ? section
      : "",
  };
}
export function readGuideTarget(hash = window.location.hash) {
  const [chapter, section] = hash.replace(/^#/, "").split("/");
  return guideTarget(chapter, section);
}
export function guideUrl(target) {
  return `/guide#${target.chapter}${target.section ? `/${target.section}` : ""}`;
}
export function GuideLink({ chapter, section = "", children }) {
  const navigate = useContext(GuideNavigation);
  const target = guideTarget(chapter, section);
  return (
    <a
      className="guideLink"
      href={guideUrl(target)}
      onClick={(event) => {
        if (
          !navigate ||
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        )
          return;
        event.preventDefault();
        navigate(target.chapter, target.section);
      }}
    >
      <span aria-hidden="true">ⓘ</span> {children}
      <span aria-hidden="true">↗</span>
    </a>
  );
}
const moduleHelp = {
  live: [
    ["Controls", "controls"],
    ["When no forecast is issued", "when-observations-are-absent"],
  ],
  map: [
    ["Map & source guide", "data-sources"],
    ["Boundary interpretation", "historical-boundaries-and-current-data"],
  ],
  quality: [
    ["How to read checks", "reviewing-checks"],
    ["Data limitations", "spatial-and-temporal-limits"],
  ],
  replay: [["How replay works", "replay-controls"]],
  legacy: [
    ["Exercise workflow", "original-workflow"],
    ["Human review rules", "human-review"],
  ],
  evidence: [
    ["Evidence guide", "evidence-available"],
    ["Model improvement rules", "controlled-improvement"],
  ],
};
export function ModuleGuideLinks({ moduleId }) {
  return (
    <div className="contextHelp" role="group" aria-label="Module explanations">
      {(moduleHelp[moduleId] || []).map(([label, section]) => (
        <GuideLink key={section} chapter={moduleId} section={section}>
          {label}
        </GuideLink>
      ))}
    </div>
  );
}
export function ProductDocs({ target, active, onNavigate, onReturn }) {
  const articleRef = useRef(null);
  const current = chapters.find((c) => c.id === target.chapter) || chapters[0];
  useLayoutEffect(() => {
    if (!active) return;
    const node = target.section
      ? articleRef.current?.querySelector(
          `[id="guide-${current.id}-${target.section}"]`,
        )
      : articleRef.current?.querySelector("h1");
    node?.focus({ preventScroll: true });
    if (target.section)
      node?.scrollIntoView({ block: "start", behavior: "instant" });
    else window.scrollTo({ top: 0, behavior: "instant" });
  }, [active, target, current.id]);
  return (
    <div className="docsLayout">
      <aside className="docsRail">
        <p>PRODUCT GUIDE</p>
        <button className="guideReturn" onClick={onReturn}>
          ← Back to workspace
        </button>
        {chapters.map((c, i) => (
          <button
            key={c.id}
            className={c.id === current.id ? "active" : ""}
            aria-current={c.id === current.id ? "page" : undefined}
            onClick={() => onNavigate(c.id)}
          >
            <small>{String(i + 1).padStart(2, "0")}</small>
            {c.title}
          </button>
        ))}
      </aside>
      <article className="docsArticle" ref={articleRef}>
        <div className="docsMeta">
          CITYSHIELD / PRODUCT DOCUMENTATION <span>01.0</span>
        </div>
        <p className="eyebrow">{current.en}</p>
        <h1 tabIndex={-1}>{current.title}</h1>
        <p className="docsIntro">{current.intro}</p>
        <div className="docsBlocks">
          {current.blocks.map(([title, text], i) => {
            const id = sectionId(title);
            return (
              <section
                key={id}
                id={`guide-${current.id}-${id}`}
                tabIndex={-1}
                className={target.section === id ? "guideTarget" : ""}
                aria-labelledby={`guide-heading-${current.id}-${id}`}
              >
                <span>{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <h2 id={`guide-heading-${current.id}-${id}`}>{title}</h2>
                  <p>{text}</p>
                </div>
              </section>
            );
          })}
        </div>
        <button className="docsOpen" onClick={onReturn}>
          Back to workspace <span>↗</span>
        </button>
        <footer>
          Historical observations, derived data, model assumptions and simulated
          results are labelled separately.
        </footer>
      </article>
    </div>
  );
}
