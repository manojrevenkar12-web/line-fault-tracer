import { int, pct } from "../../app/theme";
import type { Run } from "../../shared/types";

const METHODS = { identifiers: "Identifiers only", words: "Words + glossary", spelling: "Character n-grams", hybrid: "Hybrid (used)" } as const;

export function Scoreboard({ run }: { run: Run }) {
  const t = run.trace;
  const i = run.ingest;
  const a = run.agent;
  const clocks = Object.entries(i.clock);
  return (
    <div className="scoreboard">
      <div className="tally" aria-label="Right machine and right cause">
        {(
          [
            ["Go to the alarming machine", t.first_alarm],
            ["Tracer on raw data", t.raw],
            ["Tracer", t.tracer],
          ] as const
        ).map(([label, x]) => (
          <div key={label} className={label === "Tracer" ? "tally-item lead" : "tally-item"}>
            <span className="tally-n">
              {x.right}
              <small>/{x.of}</small>
            </span>
            <span className="tally-label">{label}</span>
          </div>
        ))}
        <p className="muted tally-note">
          Right machine and right cause. False alarms on {t.controls.n} reports where nothing was wrong: tracer{" "}
          {t.controls.tracer_false_alarms}, raw data {t.controls.raw_false_alarms}.
        </p>
      </div>

      <div className="board">
        <h3>What the data pipes did</h3>
        <table>
          <tbody>
            <tr>
              <th scope="row">Messages</th>
              <td>{int(i.messages)}</td>
            </tr>
            <tr>
              <th scope="row">Duplicates removed</th>
              <td>
                {int(i.duplicates.removed)} of {int(i.duplicates.injected)}
              </td>
            </tr>
            <tr>
              <th scope="row">Device clocks off</th>
              <td>
                {clocks.map(([d, c]) => `${d} ${c.true_s > 0 ? "+" : ""}${c.true_s} s`).join(", ") || "none"}; worst error {i.clock_max_error_s} s
              </td>
            </tr>
            <tr>
              <th scope="row">Failed reads caught</th>
              <td>
                {int(i.sentinels.caught)} of {int(i.sentinels.injected)}
              </td>
            </tr>
            <tr>
              <th scope="row">Unit changes converted</th>
              <td>{int(i.converted)} readings</td>
            </tr>
            <tr>
              <th scope="row">Connection drops found</th>
              <td>
                {i.outages.found} of {i.outages.injected}
              </td>
            </tr>
            <tr>
              <th scope="row">Unmapped tags held back</th>
              <td>{i.quarantine.length ? i.quarantine.map((q) => `${q.tag} (suggests ${q.suggestion})`).join(", ") : "none"}</td>
            </tr>
            <tr className="sum">
              <th scope="row">Readings that match the sensor</th>
              <td>
                {pct(i.values.clean.share, 2)} clean, {pct(i.values.raw.share)} raw
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="board">
        <h3>Search over manuals and tickets</h3>
        <table>
          <thead>
            <tr>
              <th scope="col">Ranking</th>
              <th scope="col">Found in top 5</th>
              <th scope="col">MRR</th>
            </tr>
          </thead>
          <tbody>
            {(Object.keys(METHODS) as (keyof typeof METHODS)[]).map((k) => (
              <tr key={k} className={k === "hybrid" ? "sum" : ""}>
                <th scope="row">{METHODS[k]}</th>
                <td>
                  {run.search[k].hit_at_5} of {run.search[k].of}
                </td>
                <td>{run.search[k].mrr.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="board">
        <h3>Assistant</h3>
        <table>
          <tbody>
            <tr>
              <th scope="row">Right and quoting a source</th>
              <td>
                {a.right_and_cited} of {a.questions}
              </td>
            </tr>
            <tr>
              <th scope="row">Operators refused a ticket</th>
              <td>
                {a.permissions.operator_refused} of {a.permissions.operator_asks}
              </td>
            </tr>
            <tr>
              <th scope="row">Leads' tickets on the root machine</th>
              <td>
                {a.permissions.lead_opened_on_root} of {a.permissions.lead_asks}
              </td>
            </tr>
            <tr>
              <th scope="row">Machine changes refused</th>
              <td>
                {a.control.refused_without_tools} of {a.control.asks}
              </td>
            </tr>
            <tr>
              <th scope="row">Planted instruction followed</th>
              <td>{a.injection.followed}</td>
            </tr>
            <tr className="sum">
              <th scope="row">Permission violations</th>
              <td>{a.permission_violations}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
