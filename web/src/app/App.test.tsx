import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import raw from "../../public/data/console.json";
import type { Console } from "../shared/types";
import { App } from "./App";

const data = raw as unknown as Console;

function mount() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <App />
    </QueryClientProvider>,
  );
}

const ok = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));

afterEach(() => vi.unstubAllGlobals());

describe("console", () => {
  it("shows a skeleton while the data loads", () => {
    vi.stubGlobal("fetch", () => new Promise(() => {}));
    mount();
    expect(screen.getByLabelText("Loading")).toBeTruthy();
  });

  it("explains a failed load and retries", async () => {
    const f = vi.fn().mockResolvedValueOnce(new Response("", { status: 500 })).mockImplementation(() => ok(data));
    vi.stubGlobal("fetch", f);
    mount();
    await screen.findByRole("alert");
    fireEvent.click(screen.getByText("Retry"));
    await waitFor(() => expect(screen.getAllByText(/alarmed/).length).toBeGreaterThan(0));
  });

  it("says what to do when a run has no incidents", async () => {
    const empty = { ...data, dev: { ...data.dev, incidents: [] } };
    vi.stubGlobal("fetch", () => ok(empty));
    mount();
    expect(await screen.findByText(/has no incidents/)).toBeTruthy();
  });

  it("opens on an incident whose fault started somewhere else, and switches on click", async () => {
    vi.stubGlobal("fetch", () => ok(data));
    mount();
    const first = data.dev.incidents.find((i) => i.symptom !== i.root)!;
    expect((await screen.findByRole("heading", { level: 1 })).textContent).toMatch(`The fault started at ${first.tracer.root}`);
    const other = data.dev.incidents.find((i) => i.symptom === i.root)!;
    fireEvent.click(screen.getByTitle(new RegExp(`^${other.id}:`)));
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 }).textContent).toMatch(`${other.symptom} alarmed, and the fault is there`));
    expect(screen.getByText(data.dev.answers[other.id].question)).toBeTruthy();
  });

  it("shows the scoreboard from the report", async () => {
    vi.stubGlobal("fetch", () => ok(data));
    mount();
    const t = data.dev.trace;
    expect(await screen.findByText(`${t.symptom_not_at_root} of ${t.incidents} faults started at another machine than the one that alarmed.`)).toBeTruthy();
    expect(screen.getByText("Permission violations").nextSibling?.textContent).toBe(String(data.dev.agent.permission_violations));
  });
});
