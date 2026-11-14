import type { Incident } from "../../shared/types";

export function IncidentRail({
  incidents,
  kinds,
  selected,
  onSelect,
}: {
  incidents: Incident[];
  kinds: Record<string, string>;
  selected: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="rail" role="group" aria-label="Incidents, in the order they happened">
      {incidents.map((inc) => (
        <button
          key={inc.id}
          className={`rail-cell${inc.tracer.right ? "" : " miss"}`}
          aria-pressed={inc.id === selected}
          title={`${inc.id}: ${kinds[inc.kind] ?? inc.kind}${inc.tracer.right ? "" : " (tracer wrong)"}`}
          onClick={() => onSelect(inc.id)}
        >
          <span className="rail-id">{inc.id.slice(1)}</span>
          <span className="rail-at">{inc.symptom}</span>
        </button>
      ))}
    </div>
  );
}
