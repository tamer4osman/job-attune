"use client";

import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { api, type AuditDecision, type ExportFile, type RunResults } from "@/lib/attune";
import { AlertTriangle, CheckCircle2, Download, FileDown, FileCheck2, Fingerprint, Loader2, ShieldCheck } from "lucide-react";

const KIND_BADGE: Record<string, { label: string; cls: string }> = {
  unreadable_document: { label: "blocking", cls: "border-rose-300 bg-rose-50 text-rose-700" },
  shortlist_band: { label: "review band", cls: "border-amber-300 bg-amber-50 text-amber-800" },
  tie_unresolved: { label: "near-tie", cls: "border-amber-300 bg-amber-50 text-amber-800" },
  rank_conflict: { label: "rank conflict", cls: "border-amber-300 bg-amber-50 text-amber-800" },
  score_advisory: { label: "advisory", cls: "border-teal-200 bg-teal-50 text-teal-800" },
  noul_kernel_advisory: { label: "advisory", cls: "border-teal-200 bg-teal-50 text-teal-800" },
  low_confidence_extraction: { label: "advisory", cls: "border-teal-200 bg-teal-50 text-teal-800" },
};

export default function Governance({
  results,
  decisions,
  exports: exportFiles,
  onDecision,
  reviewer,
  onReviewerChange,
  pseudonymous,
  onPseudonymousChange,
}: {
  results: RunResults;
  decisions: AuditDecision[];
  exports: ExportFile[];
  onDecision: () => void;
  reviewer: string;
  onReviewerChange: (v: string) => void;
  pseudonymous: boolean;
  onPseudonymousChange: (v: boolean) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const byRef = useMemo(() => Object.fromEntries(results.candidates.map((c) => [c.candidate_ref, c])), [results.candidates]);

  async function resolve(item: { kind: string; candidate_ref: string | null }, decision: "acknowledge" | "escalate_manual") {
    if (resolving) return; // audit JSONL is append-only: never double-append
    setResolving(true);
    setMsg(null);
    try {
      await api("/api/audit", {
        method: "POST",
        body: JSON.stringify({ run_id: results.run_id, action: "resolve", kind: item.kind, candidate_ref: item.candidate_ref, decision, reviewer }),
      });
      onDecision();
      setMsg(`Recorded: ${decision === "acknowledge" ? "acknowledged" : "escalated for manual review"}.`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Recording the decision failed");
    } finally {
      setResolving(false);
    }
  }

  async function exportPdfs() {
    setBusy(true);
    setMsg(null);
    try {
      await api("/api/report", { method: "POST", body: JSON.stringify({ run_id: results.run_id, pseudonymous }) });
      setMsg("PDF reports generated - download them below.");
      onDecision();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Export failed");
    } finally {
      setBusy(false);
    }
  }

  const manifest = results.audit?.manifest;
  const det = results.determinism;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card className="min-w-0 border-slate-200 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <AlertTriangle className="h-4 w-4 text-amber-600" /> Review queue
          </CardTitle>
          <CardDescription>
            Items the calibrated confidence floors flagged. Blocking items gate exports; advisory items inform the recruiter.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-2 flex items-center gap-2">
            <Label htmlFor="governance-reviewer" className="shrink-0 text-xs text-slate-500">Reviewer</Label>
            <Input
              id="governance-reviewer"
              value={reviewer}
              onChange={(e) => onReviewerChange(e.target.value)}
              placeholder="Your name (recorded with each decision)"
              className="h-7 text-xs"
            />
          </div>
          <ScrollArea className="max-h-96 pr-2">
            <div className="space-y-2">
              {results.review_queue.length === 0 && <p className="text-sm text-muted-foreground">Nothing flagged.</p>}
              {results.review_queue.map((q, i) => {
                const badge = KIND_BADGE[q.kind] ?? { label: q.kind, cls: "border-slate-200 text-slate-600" };
                const cand = q.candidate_ref ? byRef[q.candidate_ref] : null;
                return (
                  <div key={i} className="rounded-lg border border-slate-100 p-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className={`text-[10px] ${badge.cls}`}>{badge.label}</Badge>
                      <span className="text-xs font-semibold">{cand ? cand.folder_name : q.kind}</span>
                      <span className="text-[10px] text-slate-400">
                        {q.primitive} | conf {q.confidence?.toFixed(2)} vs floor {q.floor?.toFixed(2)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs leading-snug text-muted-foreground">{q.detail}</p>
                    <div className="mt-1.5 flex gap-1.5">
                      <Button size="sm" variant="outline" className="h-6 px-2 text-[11px]" disabled={resolving} onClick={() => resolve(q, "acknowledge")}>
                        Acknowledge
                      </Button>
                      <Button size="sm" variant="outline" className="h-6 px-2 text-[11px]" disabled={resolving} onClick={() => resolve(q, "escalate_manual")}>
                        Manual review
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      <div className="min-w-0 space-y-4">
        <Card className="min-w-0 border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <FileDown className="h-4 w-4 text-emerald-700" /> PDF report export
            </CardTitle>
            <CardDescription>Batch report with full ranking + one report per candidate. Pseudonymous by default.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <Switch id="pseudo" checked={pseudonymous} onCheckedChange={onPseudonymousChange} />
              <Label htmlFor="pseudo" className="text-sm">Pseudonymous reports (refs only, no folder names)</Label>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={exportPdfs} disabled={busy} className="gap-1.5 bg-emerald-700 hover:bg-emerald-800">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileCheck2 className="h-4 w-4" />} Generate PDF reports
              </Button>
              {exportFiles.length > 0 && (
                <span className="text-xs text-muted-foreground">{exportFiles.length} files ready</span>
              )}
            </div>
            {msg && <p className="text-xs text-emerald-800">{msg}</p>}
            {exportFiles.length > 0 && (
              <div className="space-y-1.5">
                {exportFiles.map((f) => (
                  <div key={f.file} className="flex items-center gap-2 text-xs">
                    <Download className="h-3.5 w-3.5 shrink-0 text-emerald-700" />
                    <a
                      className="min-w-0 flex-1 truncate font-mono text-emerald-800 underline-offset-2 hover:underline"
                      href={`/api/report?run_id=${encodeURIComponent(results.run_id)}&file=${encodeURIComponent(f.file)}`}
                      download
                    >
                      {f.kind === "batch" ? "Batch report (ranking + all candidates)" : `Candidate ${f.ref}`}
                    </a>
                    <span className="text-slate-400">{(f.sha256 ?? "").slice(0, 8)}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Fingerprint className="h-4 w-4 text-emerald-700" /> Run manifest &amp; determinism
            </CardTitle>
            <CardDescription>GDPR audit basis: replay-safe, local-only, fully hashed.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <Badge className={det?.identical ? "bg-emerald-700 text-white" : "bg-rose-700 text-white"}>
                <ShieldCheck className="mr-1 h-3 w-3" /> replay {det?.identical ? "PASS" : "FAIL"}
              </Badge>
              <span className="font-mono text-[10px] text-slate-500">{det?.pass1_sha256?.slice(0, 16)}...</span>
            </div>
            <Separator />
            {[
              ["OmniDecide version", manifest?.omnidecide_version],
              ["Engine version", manifest?.engine_version],
              ["Floors data version", manifest?.floors_data_version],
              ["Main folder", manifest?.main_folder],
              ["Profile sha256", manifest?.profile_sha256?.slice(0, 20) + "..."],
              ["Engine runtime", `${manifest?.elapsed_seconds ?? 0}s`],
            ].map(([k, v]) => (
              <div key={k as string} className="flex items-center justify-between gap-3">
                <span className="text-slate-500">{k}</span>
                <span className="min-w-0 truncate text-right font-mono">{v as string}</span>
              </div>
            ))}
            <Separator />
            <p className="text-slate-500">Floors in effect (editable floors-as-data):</p>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(manifest?.floors_table ?? {}).map(([k, v]) => (
                <Badge key={k} variant="secondary" className="font-mono text-[10px]">
                  {k} {v}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-200 shadow-sm lg:col-span-2">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <CheckCircle2 className="h-4 w-4 text-emerald-700" /> Human decision log
          </CardTitle>
          <CardDescription>Sign-offs and review resolutions - appended, immutable, JSONL on disk.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {decisions.length === 0 && <p className="text-sm text-muted-foreground">No human decisions recorded yet.</p>}
          {decisions.map((d, i) => {
            const cand = d.candidate_ref ? byRef[d.candidate_ref] : null;
            return (
              <div key={i} className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-100 px-2.5 py-1.5 text-xs">
                <Badge variant="secondary" className="text-[10px]">{d.action}</Badge>
                <span className="font-semibold">{cand ? cand.folder_name : d.kind ?? "-"}</span>
                <span className="text-slate-500">{d.decision}</span>
                <span className="text-slate-400">by {d.reviewer}</span>
                <span className="ml-auto font-mono text-[10px] text-slate-400">{d.at}</span>
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
