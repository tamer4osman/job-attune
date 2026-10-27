"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/attune";
import { AlertTriangle, ArrowRight, CheckCircle2, Cpu, Loader2, ShieldCheck } from "lucide-react";

interface ProgressState {
  stage: string;
  pct: number;
  message: string;
}

const STAGE_ORDER = ["boot", "scan", "gates", "evidence", "scoring", "decisions", "verify", "done"] as const;

const STAGE_LABELS: Record<string, string> = {
  boot: "Engine starting",
  scan: "Scanning candidate folders",
  gates: "Text extraction + readability gates",
  evidence: "Evidence extraction (OmniDecide extract)",
  scoring: "Scoring + aggregation",
  decisions: "Shortlist / tie-break / ranking",
  verify: "Determinism verification (second pass)",
  done: "Complete",
};

const MAX_POLL_FAILURES = 5;

export default function RunMonitor({
  runId,
  onDone,
}: {
  runId: string | null;
  onDone: () => void;
}) {
  const [progress, setProgress] = useState<ProgressState | null>(null);
  const [finished, setFinished] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const failuresRef = useRef(0);

  useEffect(() => {
    if (!runId || finished || failed !== null) return;
    let stop = false;
    let doneTimer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      try {
        const p = await api<ProgressState>(`/api/run/status?run_id=${encodeURIComponent(runId)}`);
        if (stop) return;
        failuresRef.current = 0;
        setProgress(p);
        if (p.stage === "error") {
          setFailed(p.message || "The screening run failed.");
        } else if (p.stage === "done") {
          setFinished(true);
          // guard the delayed hand-off: a reset inside the 600 ms window must
          // not yank the wizard back to the results step
          doneTimer = setTimeout(onDone, 600);
        }
      } catch {
        failuresRef.current += 1;
        if (!stop && failuresRef.current >= MAX_POLL_FAILURES) {
          setFailed(`Lost contact with the run after ${MAX_POLL_FAILURES} failed polls - it may have crashed.`);
        }
      }
    };
    tick();
    const iv = setInterval(tick, 900);
    return () => {
      stop = true;
      clearInterval(iv);
      if (doneTimer) clearTimeout(doneTimer);
    };
  }, [runId, finished, failed, onDone]);

  const stageIdx = STAGE_ORDER.indexOf((progress?.stage ?? "boot") as (typeof STAGE_ORDER)[number]);
  const effectiveIdx = stageIdx === -1 ? 0 : stageIdx;

  return (
    <Card className={`border-emerald-900/10 shadow-sm ${failed ? "border-rose-300" : ""}`}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          {failed ? <AlertTriangle className="h-5 w-5 text-rose-600" /> : <Cpu className="h-5 w-5 text-emerald-700" />}
          Screening run {failed ? "failed" : finished ? "complete" : "in progress"}
        </CardTitle>
        <CardDescription>
          Run ID <span className="font-mono">{runId}</span> - the pipeline executes fully locally and runs twice to prove deterministic replay.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {failed ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50/60 p-3 text-sm text-rose-900">
            {failed}
          </div>
        ) : (
          <>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium">{progress ? STAGE_LABELS[progress.stage] ?? progress.stage : "Starting engine..."}</span>
                <span className="text-muted-foreground">{Math.round(progress?.pct ?? 0)}%</span>
              </div>
              <Progress value={progress?.pct ?? 0} className="h-2.5 [&>div]:bg-emerald-600" />
              <p className="text-xs text-muted-foreground">{progress?.message ?? "Booting the OmniDecide kernel..."}</p>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {STAGE_ORDER.filter((k) => k !== "boot" && k !== "done").map((k, i) => {
                const done = effectiveIdx >= STAGE_ORDER.indexOf("done") || effectiveIdx > i;
                const active = !done && effectiveIdx === i;
                return (
                  <div key={k} className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${done ? "border-emerald-200 bg-emerald-50/60 text-emerald-900" : active ? "border-emerald-300 bg-white" : "border-slate-100 bg-slate-50 text-slate-400"}`}>
                    {done ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700" /> : active ? <Loader2 className="h-3.5 w-3.5 animate-spin text-emerald-700" /> : <span className="h-3.5 w-3.5 rounded-full border border-slate-300" />}
                    {STAGE_LABELS[k]}
                  </div>
                );
              })}
            </div>
          </>
        )}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-700" />
            Six OmniDecide primitives in use: noul, extract, score, choice, compare, rank
          </div>
          {finished && (
            <Button onClick={onDone} className="gap-1.5 bg-emerald-700 hover:bg-emerald-800">
              View results <ArrowRight className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
