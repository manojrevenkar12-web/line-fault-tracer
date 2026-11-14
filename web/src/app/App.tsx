import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { IncidentRail } from "../features/incidents/IncidentRail";
import { Answer } from "../features/lanes/Answer";
import { Lanes } from "../features/lanes/Lanes";
import { Verdicts } from "../features/lanes/Verdicts";
import { LineSchematic, headline } from "../features/line/LineSchematic";
import { Scoreboard } from "../features/scoreboard/Scoreboard";
import { useConsole } from "../shared/api";
import type { Run } from "../shared/types";
import { Empty, ErrorState, Section, Segmented, Skeleton } from "../shared/ui";
import { motion as m } from "./theme";

type Which = "dev" | "heldout";

function Line({ run }: { run: Run }) {
  const [picked, setPicked] = useState<string | null>(null);
  if (!run.incidents.length) return <Empty>This run has no incidents. Add faults under [kinds] in the world config and run scripts/evaluate.py.</Empty>;
  const incident = run.incidents.find((i) => i.id === picked) ?? run.incidents.find((i) => i.symptom !== i.root) ?? run.incidents[0];
  return (
    <>
      <div className="hero">
        <AnimatePresence mode="wait" initial={false}>
          <motion.h1 key={`${run.world}-${incident.id}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={m.swap}>
            {headline(incident)}
          </motion.h1>
        </AnimatePresence>
        <div className="schematic-scroll">
          <LineSchematic flow={run.flow} incident={incident} />
        </div>
      </div>
      <IncidentRail incidents={run.incidents} kinds={run.kinds} selected={incident.id} onSelect={setPicked} />
      <div className="detail">
        <Section
          id="lanes"
          title={`The ${run.settings.scan_from_min} minutes before the alarm, machine by machine`}
          lede={`Searched ${incident.search === "here" ? "at the machine itself" : `${incident.search} from ${incident.symptom}`}, in the order of the line.`}
        >
          <Lanes incident={incident} minutes={run.settings.scan_from_min} threshold={run.settings.z_threshold} />
        </Section>
        <aside className="side">
          <Verdicts incident={incident} kinds={run.kinds} />
          <Answer answer={run.answers[incident.id]} />
        </aside>
      </div>
    </>
  );
}

export function App() {
  const q = useConsole();
  const [which, setWhich] = useState<Which>("dev");
  const run = q.data ? (which === "heldout" && q.data.heldout ? q.data.heldout : q.data.dev) : null;
  return (
    <div className="page">
      <header className="masthead">
        <span className="product">line-fault-tracer</span>
        {q.data && (
          <Segmented<Which>
            label="Which line"
            options={q.data.heldout ? { dev: "Dev line", heldout: "Held-out line" } : { dev: "Dev line" } as Record<Which, string>}
            value={which}
            onChange={setWhich}
          />
        )}
      </header>
      <main>
        {q.isPending && <Skeleton />}
        {q.isError && <ErrorState message={(q.error as Error).message} onRetry={() => q.refetch()} />}
        {run && (
          <>
            <Line key={run.world} run={run} />
            <Section
              id="scores"
              title={`All ${run.trace.incidents} incidents on the ${run.world === "dev" ? "dev" : "held-out"} line`}
              lede={`${run.trace.symptom_not_at_root} of ${run.trace.incidents} faults started at another machine than the one that alarmed.`}
            >
              <Scoreboard run={run} />
            </Section>
          </>
        )}
      </main>
    </div>
  );
}
