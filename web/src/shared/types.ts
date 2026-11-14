export type Verdict = { root: string | null; cause: string | null; right: boolean; right_root: boolean };

export type Lane = { asset: string; signal: string; z: (number | null)[]; onset_min: number | null };

export type Incident = {
  id: string;
  kind: string;
  known_kind: boolean;
  weak: boolean;
  symptom: string;
  root: string;
  search: "upstream" | "downstream" | "here";
  true_onset_min: number;
  tracer: Verdict & { verdict: string; onset_error_min: number | null };
  raw: Verdict;
  first_alarm: Verdict;
  lanes: Lane[];
};

export type Tally = { right: number; right_root: number; of: number };

export type Method = { hit_at_5: number; manual_at_5: number; mrr: number; precision_at_5: number; of: number };

export type Run = {
  world: string;
  line: { assets: number; signals: number; days: number; sample_s: number };
  settings: { z_threshold: number; scan_from_min: number; smooth: number; consecutive: number };
  flow: string[];
  assets: Record<string, string>;
  trace: {
    incidents: number;
    symptom_not_at_root: number;
    tracer: Tally;
    raw: Tally;
    first_alarm: Tally;
    onset_error_min_median: number | null;
    controls: { n: number; tracer_false_alarms: number; raw_false_alarms: number };
  };
  incidents: Incident[];
  ingest: {
    messages: number;
    duplicates: { injected: number; removed: number };
    sentinels: { injected: number; caught: number };
    clock: Record<string, { true_s: number; estimated_s: number; error_s: number }>;
    clock_max_error_s: number;
    converted: number;
    outages: { injected: number; found: number };
    late: { injected: number; flagged: number };
    stuck_flagged: number;
    quarantine: { tag: string; messages: number; suggestion: string | null; suggestion_right: boolean }[];
    values: { clean: { share: number }; raw: { share: number } };
  };
  search: Record<"identifiers" | "words" | "spelling" | "hybrid", Method>;
  agent: {
    questions: number;
    right: number;
    right_and_cited: number;
    permission_violations: number;
    permissions: { operator_asks: number; operator_refused: number; lead_asks: number; lead_opened_on_root: number };
    control: { asks: number; refused_without_tools: number };
    injection: { planted: number; retrieved: number; followed: number };
  };
  answers: Record<string, { question: string; answer: string; sources: string[] }>;
  kinds: Record<string, string>;
};

export type Console = { dev: Run; heldout: Run | null };
