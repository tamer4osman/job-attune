"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, toEngineProfile, type AuditDecision, type ExportFile, type JobProfile, type RunResults, type ScanResult } from "@/lib/attune";
import FolderPicker from "@/components/attune/folder-picker";
import JobProfileEditor from "@/components/attune/job-profile";
import RunMonitor from "@/components/attune/run-monitor";
import RankingBoard, { CandidateCards, StatCards } from "@/components/attune/ranking-board";
import OverviewCharts from "@/components/attune/overview-charts";
import PositionReport from "@/components/attune/position-report";
import Governance from "@/components/attune/governance";
import { EMPTY_PROFILE } from "@/components/attune/defaults";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import {
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  Crown,
  FileSignature,
  FolderOpen,
  ListOrdered,
  RotateCcw,
  ShieldCheck,
  UserSearch,
} from "lucide-react";

const STEPS = [
  { id: 1, label: "Candidates", icon: FolderOpen },
  { id: 2, label: "Job profile", icon: FileSignature },
  { id: 3, label: "Run", icon: BrainCircuit },
  { id: 4, label: "Results", icon: BarChart3 },
];

export default function Home() {
  const [step, setStep] = useState(1);
  const [scanned, setScanned] = useState<ScanResult | null>(null);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [profile, setProfile] = useState<JobProfile>(EMPTY_PROFILE);
  const [folder, setFolder] = useState<string>("");
  const [roleOverrides, setRoleOverrides] = useState<Record<string, string>>({});
  const [runId, setRunId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [results, setResults] = useState<RunResults | null>(null);
  const [decisions, setDecisions] = useState<AuditDecision[]>([]);
  const [exportFiles, setExportFiles] = useState<ExportFile[]>([]);
  const [startError, setStartError] = useState<string | null>(null);
  const [resultsError, setResultsError] = useState<string | null>(null);
  // shared governance state: both Review and Audit tabs render a Governance
  // instance; lifting it keeps reviewer name / pseudonymous toggle consistent
  const [reviewer, setReviewer] = useState("");
  const [pseudonymous, setPseudonymous] = useState(true);
  const runIdRef = useRef<string | null>(null);

  useEffect(() => {
    runIdRef.current = runId;
  }, [runId]);

  const scan = useCallback(async (p: string) => {
    setScanning(true);
    setScanError(null);
    try {
      const data = await api<ScanResult>("/api/scan", { method: "POST", body: JSON.stringify({ folder: p }) });
      setScanned(data);
      setFolder(data.folder);
    } catch (e) {
      setScanned(null);
      setScanError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  }, []);

  const startRun = useCallback(async () => {
    if (starting) return; // double-submit guard: never spawn two engines
    setStarting(true);
    setStartError(null);
    try {
      const engineProfile = toEngineProfile(profile, roleOverrides, true);
      const d = await api<{ runId: string; runDir?: string }>("/api/run", {
        method: "POST",
        body: JSON.stringify({ folder, profile: engineProfile }),
      });
      setResults(null);
      setExportFiles([]);
      setRunId(d.runId);
      setStep(3);
    } catch (e) {
      setStartError(e instanceof Error ? e.message : "Run start failed");
    } finally {
      setStarting(false);
    }
  }, [folder, profile, roleOverrides, starting]);

  const loadResults = useCallback(async (id: string) => {
    const d = await api<{ results: RunResults; decisions: AuditDecision[]; exports: ExportFile[] }>(
      `/api/run/results?run_id=${encodeURIComponent(id)}`,
    );
    if (runIdRef.current !== id) return; // stale response guard (reset/new run)
    setResults(d.results);
    setDecisions(d.decisions ?? []);
    setExportFiles(d.exports ?? []);
  }, []);

  const finishRun = useCallback(async () => {
    setResultsError(null);
    if (!runId) {
      setStep(4);
      return;
    }
    try {
      await loadResults(runId);
    } catch (e) {
      if (runIdRef.current !== runId) return; // superseded meanwhile
      setResultsError(e instanceof Error ? e.message : "Failed to load results");
    }
    setStep(4);
  }, [runId, loadResults]);

  const refreshAudit = useCallback(async () => {
    if (runId) await loadResults(runId).catch(() => {});
  }, [runId, loadResults]);

  const reset = () => {
    setStep(1);
    setScanned(null);
    setResults(null);
    setRunId(null);
    setExportFiles([]);
    setDecisions([]);
    setRoleOverrides({});
    setResultsError(null);
    setStartError(null);
  };

  return (
    <div className="flex min-h-screen flex-col bg-slate-50/70">
      {/* header */}
      <header className="sticky top-0 z-40 border-b border-emerald-950/20 bg-gradient-to-r from-slate-900 via-emerald-950 to-slate-900 text-white shadow-md">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/20 ring-1 ring-emerald-400/40">
            <UserSearch className="h-5 w-5 text-emerald-300" />
          </div>
          <div className="mr-auto">
            <p className="text-base font-bold leading-tight tracking-tight">
              Job Attune
              <span className="ml-2 text-xs font-medium text-emerald-300/90">Hire for aptitude - GDPR-safe resume screening</span>
            </p>
            <p className="text-[11px] leading-tight text-slate-300/80">
              Local · deterministic · omnidecide-c C11 kernel with calibrated confidence floors
            </p>
          </div>
          <Badge variant="outline" className="gap-1 border-emerald-400/40 bg-emerald-500/10 text-emerald-200">
            <ShieldCheck className="h-3 w-3" /> 100% local processing
          </Badge>
          {(results || runId) && (
            <Button variant="outline" size="sm" onClick={reset} className="gap-1 border-slate-600 bg-white/5 text-slate-200 hover:bg-white/10 hover:text-white">
              <RotateCcw className="h-3.5 w-3.5" /> New run
            </Button>
          )}
        </div>
      </header>

      {/* stepper */}
      <nav aria-label="Workflow steps" className="mx-auto w-full max-w-7xl px-4 pt-5 sm:px-6">
        <ol className="flex flex-wrap items-center gap-2">
          {STEPS.map((s, i) => {
            const Icon = s.icon;
            const state = step === s.id ? "current" : step > s.id ? "done" : "todo";
            return (
              <li key={s.id} className="flex items-center gap-2">
                <button
                  onClick={() => {
                    if (state === "done") setStep(s.id);
                  }}
                  className={cn(
                    "flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition",
                    state === "current" && "border-emerald-700 bg-emerald-700 text-white shadow-sm",
                    state === "done" && "cursor-pointer border-emerald-200 bg-emerald-50 text-emerald-800 hover:bg-emerald-100",
                    state === "todo" && "border-slate-200 bg-white text-slate-400",
                  )}
                  disabled={state === "todo"}
                  aria-current={state === "current" ? "step" : undefined}
                >
                  {state === "done" ? <CheckCircle2 className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                  <span className="font-medium">{s.label}</span>
                </button>
                {i < STEPS.length - 1 && <span className="hidden h-px w-6 bg-slate-300 sm:block" aria-hidden />}
              </li>
            );
          })}
        </ol>
      </nav>

      {/* main */}
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-5 sm:px-6">
        {step === 1 && (
          <FolderPicker
            scanned={scanned}
            scanning={scanning}
            error={scanError}
            onScan={scan}
            onRoleChange={(relPath, role) => {
              setRoleOverrides((prev) => ({ ...prev, [relPath]: role }));
              setScanned((prev) => {
                if (!prev) return prev;
                return {
                  ...prev,
                  candidates: prev.candidates.map((c) => ({
                    ...c,
                    files: c.files.map((f) => (f.relPath === relPath ? { ...f, role: role as typeof f.role } : f)),
                    hasCv: c.files.some((f) => (f.relPath === relPath ? role : f.role) === "cv"),
                    hasCover: c.files.some((f) => (f.relPath === relPath ? role : f.role) === "cover"),
                  })),
                };
              });
            }}
            onConfirm={() => setStep(2)}
          />
        )}

        {step === 2 && (
          <div className="space-y-4">
            {startError && <p className="text-sm text-rose-700">{startError}</p>}
            <JobProfileEditor profile={profile} onChange={setProfile} onNext={startRun} starting={starting} />
            {starting && <p className="text-sm text-emerald-800">Starting engine...</p>}
          </div>
        )}

        {step === 3 && <RunMonitor runId={runId} onDone={finishRun} />}

        {step === 4 && !results && (
          <div className="mx-auto max-w-md space-y-3 rounded-xl border border-rose-200 bg-white p-6 text-center shadow-sm">
            <p className="text-sm font-semibold text-rose-700">Results could not be loaded</p>
            <p className="text-xs text-muted-foreground">{resultsError ?? "The run has no results yet."}</p>
            <div className="flex justify-center gap-2">
              <Button variant="outline" onClick={finishRun}>Retry</Button>
              <Button variant="outline" onClick={reset}>New run</Button>
            </div>
          </div>
        )}

        {step === 4 && results && (
          <div className="space-y-4">
            <StatCards results={results} />
            <Tabs defaultValue="overview">
              <TabsList className="flex-wrap">
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="position" className="gap-1.5">
                  <Crown className="h-3.5 w-3.5" /> Position report
                </TabsTrigger>
                <TabsTrigger value="ranking" className="gap-1.5">
                  <ListOrdered className="h-3.5 w-3.5" /> Ranking
                </TabsTrigger>
                <TabsTrigger value="candidates">Candidates</TabsTrigger>
                <TabsTrigger value="review" className="gap-1.5">
                  Review
                  {results.review_queue.length > 0 && (
                    <Badge variant="outline" className="ml-1 border-amber-300 bg-amber-50 px-1 text-[10px] text-amber-800">
                      {results.review_queue.length}
                    </Badge>
                  )}
                </TabsTrigger>
                <TabsTrigger value="audit">Audit &amp; export</TabsTrigger>
              </TabsList>
              <TabsContent value="overview" className="mt-4">
                <OverviewCharts results={results} />
              </TabsContent>
              <TabsContent value="position" className="mt-4">
                <PositionReport results={results} />
              </TabsContent>
              <TabsContent value="ranking" className="mt-4">
                <RankingBoard results={results} />
              </TabsContent>
              <TabsContent value="candidates" className="mt-4">
                <CandidateCards results={results} />
              </TabsContent>
              <TabsContent value="review" className="mt-4">
                <Governance
                  results={results}
                  decisions={decisions}
                  exports={exportFiles}
                  onDecision={refreshAudit}
                  reviewer={reviewer}
                  onReviewerChange={setReviewer}
                  pseudonymous={pseudonymous}
                  onPseudonymousChange={setPseudonymous}
                />
              </TabsContent>
              <TabsContent value="audit" className="mt-4">
                <Governance
                  results={results}
                  decisions={decisions}
                  exports={exportFiles}
                  onDecision={refreshAudit}
                  reviewer={reviewer}
                  onReviewerChange={setReviewer}
                  pseudonymous={pseudonymous}
                  onPseudonymousChange={setPseudonymous}
                />
              </TabsContent>
            </Tabs>
          </div>
        )}
      </main>

      {/* sticky footer */}
      <footer className="mt-auto border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-3 text-[11px] text-slate-500 sm:px-6">
          <p>
            Job Attune v1.0.0 © 2026 Tamer Osman - Apache-2.0. Hire for aptitude. Candidate files never leave this machine: pseudonymous refs (sha256), PII redaction, replay-safe audit manifest.
          </p>
          <p>Powered by the omnidecide-c C11 kernel - floors-as-data, six primitives, human-in-the-loop.</p>
        </div>
      </footer>
    </div>
  );
}
