import { motion } from "framer-motion";
import { motion as m, schematic as s } from "../../app/theme";
import type { Incident } from "../../shared/types";

const TYPES: Record<string, string> = {
  F1: "Filler",
  C2: "Capper",
  L3: "Labeler",
  CV34: "Conveyor",
  W4: "Checkweigher",
  P5: "Case packer",
  R6: "Palletizer",
};

export function headline(inc: Incident): string {
  const t = inc.tracer;
  if (!t.root) return `${inc.symptom} alarmed. Nothing ${inc.search === "downstream" ? "after" : "before"} it left its normal band.`;
  const lead = inc.lanes.find((l) => l.asset === t.root)?.onset_min;
  const when = lead != null ? `, ${Math.max(0, Math.round(-lead))} min before the alarm` : "";
  if (t.root === inc.symptom) return `${inc.symptom} alarmed, and the fault is there${when}.`;
  return `${inc.symptom} alarmed. The fault started at ${t.root}${when}.`;
}

export function LineSchematic({ flow, incident }: { flow: string[]; incident: Incident }) {
  const gap = (s.width - flow.length * s.machineW) / (flow.length - 1);
  const x = (i: number) => i * (s.machineW + gap);
  const centre = (id: string) => x(flow.indexOf(id)) + s.machineW / 2;
  const looked = new Set(incident.lanes.map((l) => l.asset));
  const root = incident.tracer.root;
  const from = centre(incident.symptom);
  const to = root ? centre(root) : from;
  const head = Math.sign(to - from) * s.arrowHead;
  return (
    <svg
      className="schematic"
      viewBox={`0 0 ${s.width} ${s.height}`}
      role="img"
      aria-label={`Line ${flow.join(", ")}. Alarm at ${incident.symptom}. ${root ? `Traced to ${root}.` : "No root found."}`}
    >
      <line x1={0} x2={s.width} y1={s.conveyorY} y2={s.conveyorY} className="conveyor" />
      {flow.slice(0, -1).map((id, i) => (
        <path
          key={id}
          className="chevron"
          d={`M ${x(i) + s.machineW + gap / 2 - s.chevron / 2} ${s.conveyorY - s.chevron} l ${s.chevron} ${s.chevron} l ${-s.chevron} ${s.chevron}`}
        />
      ))}
      {flow.map((id, i) => {
        const cls = ["machine", looked.has(id) ? "looked" : "", id === incident.symptom ? "symptom" : "", id === root ? "root" : ""]
          .filter(Boolean)
          .join(" ");
        return (
          <g key={id} className={cls} transform={`translate(${x(i)}, ${s.conveyorY - s.machineH - s.lift})`}>
            <rect width={s.machineW} height={s.machineH} rx={s.corner} />
            <text className="machine-tag" x={s.pad} y={s.tagY}>
              {id}
            </text>
            <text className="machine-type" x={s.pad} y={s.typeY}>
              {TYPES[id] ?? id}
            </text>
            {id === incident.symptom && (
              <text className="flag flag-alarm" x={s.machineW - s.pad} y={s.flagY} textAnchor="end">
                alarm
              </text>
            )}
            {id === root && id !== incident.symptom && (
              <text className="flag flag-fault" x={s.machineW - s.pad} y={s.flagY} textAnchor="end">
                started here
              </text>
            )}
            {id === incident.root && id !== root && (
              <text className="flag flag-fault" x={s.machineW - s.pad} y={s.flagY} textAnchor="end">
                really here
              </text>
            )}
          </g>
        );
      })}
      {root && root !== incident.symptom && (
        <g className="trace-arrow">
          <motion.path
            key={incident.id}
            d={`M ${from} ${s.arrowY} L ${to} ${s.arrowY}`}
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={m.draw}
          />
          <motion.path
            key={`${incident.id}-head`}
            d={`M ${to + head} ${s.arrowY - s.arrowHead} L ${to} ${s.arrowY} L ${to + head} ${s.arrowY + s.arrowHead}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: m.draw.duration * 0.8, duration: m.swap.duration }}
          />
        </g>
      )}
    </svg>
  );
}
