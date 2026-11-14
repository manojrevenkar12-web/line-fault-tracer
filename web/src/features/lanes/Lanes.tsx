import { motion } from "framer-motion";
import { chart, motion as m } from "../../app/theme";
import type { Incident, Lane } from "../../shared/types";

const SIGNAL = (s: string) => s.split(".")[1].replace(/_/g, " ");

function Strip({ lane, minutes, threshold, kind, trueOnset }: { lane: Lane; minutes: number; threshold: number; kind: string; trueOnset: number }) {
  const n = lane.z.length;
  const x = (i: number) => (i / Math.max(n - 1, 1)) * chart.width;
  const xMin = (min: number) => ((min + minutes) / minutes) * chart.width;
  const half = chart.height / 2;
  // linear inside the normal band, logarithmic beyond it: noise stays quiet and a departure forty times the band
  // still fits
  const scale = (z: number) => {
    const a = Math.min(Math.abs(z), chart.zClip);
    const t = threshold;
    const v = a <= t ? (a / t) * chart.band : chart.band + ((1 - chart.band) * Math.log1p(a - t)) / Math.log1p(chart.zClip - t);
    return Math.sign(z) * v;
  };
  const y = (z: number) => half - scale(z) * half;
  const pts = lane.z.map((z, i) => (z == null ? null : `${x(i)},${y(z)}`));
  const segments: string[] = [];
  let cur: string[] = [];
  for (const p of pts) {
    if (p == null) {
      if (cur.length) segments.push(cur.join(" "));
      cur = [];
    } else cur.push(p);
  }
  if (cur.length) segments.push(cur.join(" "));
  const label = `${lane.asset} ${SIGNAL(lane.signal)}: ${lane.onset_min != null ? `left its band ${Math.round(-lane.onset_min)} min before the alarm` : "stayed in its band"}`;
  return (
    <svg className={`strip ${kind}`} viewBox={`0 0 ${chart.width} ${chart.height}`} preserveAspectRatio="none" role="img" aria-label={label}>
      <rect className="band" x={0} width={chart.width} y={y(threshold)} height={y(-threshold) - y(threshold)} />
      <line className="zero" x1={0} x2={chart.width} y1={half} y2={half} />
      <line className="truth" x1={xMin(trueOnset)} x2={xMin(trueOnset)} y1={0} y2={chart.height} />
      {segments.map((pts, i) => (
        <motion.polyline key={`${lane.signal}-${i}`} className="trace" points={pts} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={m.swap} />
      ))}
      {lane.onset_min != null && <line className="onset" x1={xMin(lane.onset_min)} x2={xMin(lane.onset_min)} y1={0} y2={chart.height} />}
    </svg>
  );
}

export function Lanes({ incident, minutes, threshold }: { incident: Incident; minutes: number; threshold: number }) {
  if (!incident.lanes.length) return <p className="muted">No readings on the machines this trace looked at.</p>;
  return (
    <div className="lanes">
      <div className="lanes-key">
        <span>
          <i className="key-band" /> normal band (robust z within ±{threshold})
        </span>
        <span>
          <i className="key-onset" /> where the tracer saw it leave
        </span>
        <span>
          <i className="key-truth" /> when the fault really began
        </span>
      </div>
      {incident.lanes.map((lane) => {
        const kind = lane.asset === incident.tracer.root ? "root" : lane.asset === incident.symptom ? "symptom" : "";
        return (
          <div className="lane" key={lane.asset}>
            <div className="lane-tag">
              <span className={`lane-asset ${kind}`}>{lane.asset}</span>
              <span className="lane-signal">{SIGNAL(lane.signal)}</span>
            </div>
            <Strip lane={lane} minutes={minutes} threshold={threshold} kind={kind} trueOnset={incident.true_onset_min} />
          </div>
        );
      })}
      <div className="lane-axis" aria-hidden="true">
        <span />
        <div className="axis-ticks">
          {Array.from({ length: minutes / chart.tick + 1 }, (_, i) => (
            <span key={i}>{i === minutes / chart.tick ? "alarm" : `−${minutes - i * chart.tick} min`}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
