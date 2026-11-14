import type { Incident, Verdict } from "../../shared/types";

const CAUSE: Record<string, string> = {
  nozzle_clog: "clogged nozzle",
  torque_drift: "torque drift",
  glue_cold: "cold glue",
  gripper_leak: "vacuum leak",
  conveyor_jam: "conveyor jam",
  loadcell_drift: "load cell drift",
};

function Row({ who, v }: { who: string; v: Verdict }) {
  return (
    <tr>
      <th scope="row">{who}</th>
      <td className="tag">{v.root ?? "none"}</td>
      <td>{v.cause ? CAUSE[v.cause] ?? v.cause : "cause unknown"}</td>
      <td className={v.right ? "right" : "wrong"}>{v.right ? "right" : v.right_root ? "machine right" : "wrong"}</td>
    </tr>
  );
}

export function Verdicts({ incident, kinds }: { incident: Incident; kinds: Record<string, string> }) {
  return (
    <div className="verdicts">
      <p className="truth-line">
        What really happened: <strong>{kinds[incident.kind] ?? incident.kind}</strong>
        {incident.weak ? ", a weak one" : ""}.
      </p>
      <table>
        <thead>
          <tr>
            <th scope="col">Who decides</th>
            <th scope="col">Machine</th>
            <th scope="col">Cause</th>
            <th scope="col" />
          </tr>
        </thead>
        <tbody>
          <Row who="Tracer" v={incident.tracer} />
          <Row who="Tracer on raw data" v={incident.raw} />
          <Row who="Go to the alarming machine" v={incident.first_alarm} />
        </tbody>
      </table>
    </div>
  );
}
