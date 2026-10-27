"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { api, type CandidateResult, type RunResults } from "@/lib/attune";
import { useState } from "react";
import { AlertTriangle, BadgeCheck, CheckCircle2, FileText, Gauge, GitCompareArrows, Layers, ListOrdered, MessagesSquare, ScrollText, Signature, Sparkles, UserRound } from "lucide-react";

function levelColor(level: string) {
  return {
    strong: "bg-emerald-100 text-emerald-800",
    good: "bg-teal-100 text-teal-800",
    partial: "bg-amber-100 text-amber-800",
    weak: "bg-slate-100 text-slate-600",
    none: "bg-rose-50 text-rose-600",
  }[level] ?? "bg-slate-100 text-slate-600";
}

function verdictColor(verdict: string | undefined) {
  return {
    met: "bg-emerald-100 text-emerald-800",
    partial: "bg-amber-100 text-amber-800",
    missing: "bg-rose-50 text-rose-700",
  }[verdict ?? ""] ?? "bg-slate-100 text-slate-600";
}

function tierColor(tier: string | undefined) {
  return {
    A: "border-emerald-300 bg-emerald-50 text-emerald-800",
    B: "border-amber-300 bg-amber-50 text-amber-800",
    C: "border-slate-300 bg-slate-50 text-slate-600",
  }[tier ?? ""] ?? "border-slate-300 bg-slate-50 text-slate-600";
}

export function CandidateDetailDialog({
  candidate,
  results,
  onClose,
}: {
  candidate: CandidateResult | null;
  results: RunResults;
  onClose: () => void;
}) {
  const [reviewer, setReviewer] = useState("");
  const [signMsg, setSignMsg] = useState<string | null>(null);
  if (!candidate) return null;
  const c = candidate;
  const label = c.folder_name;

  async function signOff(decision: "endorse" | "reject") {
    try {
      await api("/api/audit", {
        method: "POST",
        body: JSON.stringify({
          run_id: results.run_id,
          action: "signoff",
          candidate_ref: c.candidate_ref,
          decision,
          reviewer,
          note: `Rank #${c.rank}, overall ${c.overall}`,
        }),
      });
      setSignMsg(`Recorded: ${decision === "endorse" ? "endorsed" : "rejected"} by ${reviewer || "anonymous"} - written to the audit trail.`);
    } catch (e) {
      setSignMsg(e instanceof Error ? e.message : "Sign-off failed");
    }
  }

  return (
    <Dialog open={!!candidate} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-h-[88vh] sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2 text-lg">
            <ListOrdered className="h-5 w-5 text-emerald-700" />
            #{c.rank} {label}
            <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-800">
              {c.overall.toFixed(1)} / 100 - {c.band}
            </Badge>
            {c.shortlisted && <Badge className="bg-emerald-700 text-white hover:bg-emerald-800">shortlisted</Badge>}
            {c.tier && <Badge variant="outline" className={tierColor(c.tier)}>tier {c.tier}</Badge>}
          </DialogTitle>
          <DialogDescription>
            Ref <span className="font-mono">{c.candidate_ref}</span> (pseudonymous) - full evidence audit below.
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="max-h-[62vh] pr-3">
          <div className="space-y-4">
            <div className="rounded-lg border border-emerald-900/10 bg-emerald-50/40 p-3 text-sm leading-relaxed">
              <p className="mb-1 flex items-center gap-1.5 font-semibold text-emerald-900">
                <ScrollText className="h-4 w-4" /> Overall assessment
              </p>
              {c.overall_assessment}
            </div>

            {c.review_note && (
              <div className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
                <span><b>Review note:</b> {c.review_note}</span>
              </div>
            )}

            {c.noul_gates.some((g) => g.blocking) && (
              <div className="flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                <AlertTriangle className="h-4 w-4" /> CV could not be read automatically - treat this assessment as incomplete.
              </div>
            )}

            {c.profile_card && (
              <div>
                <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
                  <UserRound className="h-4 w-4 text-emerald-700" /> Applicant profile (auto-extracted)
                </p>
                <div className="grid gap-2 text-xs sm:grid-cols-2">
                  <div className="rounded-lg border border-slate-100 bg-white p-2.5">
                    <p className="font-semibold text-slate-700">Experience & seniority</p>
                    <p className="mt-1 text-muted-foreground">
                      {c.profile_card.experience_years != null ? `~${c.profile_card.experience_years.toFixed(1)} years (${c.profile_card.experience_basis.replace("_", " ")})` : "not detected"}
                      {" | "}{c.profile_card.seniority_estimate}
                      {c.profile_card.seniority_signal && ` - ${c.profile_card.seniority_signal}`}
                    </p>
                    {c.profile_card.career_timeline.length > 0 && (
                      <p className="mt-1 font-mono text-[10px] text-slate-400">{c.profile_card.career_timeline.map((t) => t.span).join(" | ")}</p>
                    )}
                    {c.profile_card.tenure && (
                      <p className="mt-1 text-[11px] text-slate-500">
                        Tenure: {c.profile_card.tenure.positions} spans, avg {Math.round(c.profile_card.tenure.avg_months)} mo, longest {Math.round(c.profile_card.tenure.longest_months)} mo
                      </p>
                    )}
                  </div>
                  <div className="rounded-lg border border-slate-100 bg-white p-2.5">
                    <p className="font-semibold text-slate-700">Education & languages</p>
                    <p className="mt-1 text-muted-foreground">
                      {c.profile_card.education.length > 0 ? c.profile_card.education.map((e) => `${e.level}: ${e.detail}`).join(" | ") : "no degrees detected"}
                    </p>
                    <p className="mt-1 text-muted-foreground">
                      {c.profile_card.languages.length > 0 ? c.profile_card.languages.map((l) => `${l.language} ${l.level}/${l.band}`).join(" | ") : "no language levels detected"}
                    </p>
                  </div>
                  <div className="rounded-lg border border-slate-100 bg-white p-2.5">
                    <p className="font-semibold text-slate-700">Certifications</p>
                    <p className="mt-1 text-muted-foreground">{c.profile_card.certifications.length > 0 ? c.profile_card.certifications.join(" | ") : "none detected"}</p>
                  </div>
                  {c.cohort && (
                    <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-2.5">
                      <p className="flex items-center gap-1 font-semibold text-emerald-900"><Gauge className="h-3.5 w-3.5" /> Cohort standing</p>
                      <p className="mt-1 text-emerald-900/80">
                        percentile {c.cohort.percentile_overall.toFixed(0)} | {c.cohort.delta_vs_mean >= 0 ? "+" : ""}{c.cohort.delta_vs_mean.toFixed(1)} pts vs mean | {c.cohort.delta_vs_best >= 0 ? "+" : ""}{c.cohort.delta_vs_best.toFixed(1)} vs best
                      </p>
                    </div>
                  )}
                </div>
                {c.profile_card.achievements.length > 0 && (
                  <div className="mt-2 rounded-lg border border-slate-100 bg-white p-2.5">
                    <p className="flex items-center gap-1.5 text-xs font-semibold text-slate-700"><Sparkles className="h-3.5 w-3.5 text-amber-500" /> Quantified achievements</p>
                    <ul className="mt-1 space-y-1">
                      {c.profile_card.achievements.map((a, i) => (
                        <li key={i} className="text-xs italic leading-snug text-slate-500">&ldquo;{a}&rdquo;</li>
                      ))}
                    </ul>
                  </div>
                )}
                {c.profile_card.risk_flags.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {c.profile_card.risk_flags.map((rf, i) => (
                      <p key={i} className="flex items-start gap-1.5 rounded-lg border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900">
                        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> <span><b>{rf.flag.replace(/_/g, " ")}:</b> {rf.detail}</span>
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}

            {c.interview_prompts && c.interview_prompts.length > 0 && (
              <div className="rounded-lg border border-emerald-900/10 bg-slate-50 p-3">
                <p className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold"><MessagesSquare className="h-4 w-4 text-emerald-700" /> Interview prompts</p>
                <ol className="list-inside list-decimal space-y-1 text-xs leading-snug text-slate-600">
                  {c.interview_prompts.map((p, i) => <li key={i}>{p}</li>)}
                </ol>
              </div>
            )}

            {c.skills_inventory && c.skills_inventory.length > 0 && (
              <div>
                <p className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold"><Layers className="h-4 w-4 text-emerald-700" /> Skills inventory (beyond the requirements)</p>
                <div className="flex flex-wrap gap-1.5">
                  {c.skills_inventory.map((s) => (
                    <Badge key={s.skill} variant="secondary" className="text-[10px]">
                      {s.skill} <span className="ml-1 text-slate-400">&times;{s.mentions}</span>
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            <div>
              <p className="mb-2 text-sm font-semibold">Category breakdown</p>
              <div className="space-y-1.5">
                {c.categories.map((cat) => (
                  <div key={cat.category} className="flex items-center gap-2 text-xs">
                    <span className="w-44 shrink-0 truncate">{cat.label}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full rounded-full bg-gradient-to-r from-emerald-600 to-teal-500" style={{ width: `${cat.avg * 100}%` }} />
                    </div>
                    <span className="w-10 text-right font-semibold tabular-nums">{Math.round(cat.avg * 100)}%</span>
                    {cat.score_advisory && <Badge variant="outline" className="text-[10px] text-amber-700">kernel advisory</Badge>}
                  </div>
                ))}
              </div>
              {c.values_fit !== null && (
                <p className="mt-2 text-xs text-muted-foreground">
                  Company values fit: {Math.round(c.values_fit * 100)}% of value phrases covered
                  {c.values_per_phrase.length > 0 && ` (${c.values_per_phrase.map((v) => `${v.phrase}: ${Math.round(v.coverage * 100)}%`).join(", ")})`}
                </p>
              )}
              {c.score_decomposition?.contributions && c.score_decomposition.contributions.length > 0 && (
                <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50/60 p-2.5">
                  <p className="mb-1.5 text-xs font-semibold text-slate-700">Score decomposition (points of 100)</p>
                  <div className="space-y-1">
                    {c.score_decomposition.contributions.map((d) => (
                      <div key={d.category} className="flex items-center gap-2 text-[11px]">
                        <span className="w-40 shrink-0 truncate text-muted-foreground">{d.label}</span>
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                          <div className="h-full rounded-full bg-teal-600/70" style={{ width: `${Math.min(100, d.points)}%` }} />
                        </div>
                        <span className="w-9 text-right font-semibold tabular-nums">{d.points.toFixed(1)}</span>
                      </div>
                    ))}
                    {c.score_decomposition.values_fit_points > 0 && (
                      <div className="flex items-center gap-2 text-[11px]">
                        <span className="w-40 shrink-0 truncate text-muted-foreground">Company values fit</span>
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                          <div className="h-full rounded-full bg-amber-500/70" style={{ width: `${Math.min(100, c.score_decomposition.values_fit_points)}%` }} />
                        </div>
                        <span className="w-9 text-right font-semibold tabular-nums">{c.score_decomposition.values_fit_points.toFixed(1)}</span>
                      </div>
                    )}
                    <p className="pt-0.5 text-[11px] text-slate-600">
                      Total: <b className="tabular-nums">{c.score_decomposition.sum_points.toFixed(1)}</b> / 100
                      {c.score_decomposition.note && <span className="text-amber-700"> - {c.score_decomposition.note}</span>}
                    </p>
                  </div>
                </div>
              )}
            </div>

            <Separator />
            <div>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold">Requirement evidence</p>
                {c.verdict_summary && (
                  <span className="flex items-center gap-1 text-[11px]">
                    <span className="rounded bg-emerald-100 px-1.5 py-0.5 font-bold tabular-nums text-emerald-800">{c.verdict_summary.met} met</span>
                    <span className="rounded bg-amber-100 px-1.5 py-0.5 tabular-nums text-amber-800">{c.verdict_summary.partial} partial</span>
                    <span className="rounded bg-rose-50 px-1.5 py-0.5 tabular-nums text-rose-700">{c.verdict_summary.missing} missing</span>
                    <span className="text-muted-foreground">| {c.verdict_summary.completeness_pct.toFixed(0)}% complete</span>
                  </span>
                )}
              </div>
              <div className="space-y-2">
                {c.requirements.map((r) => (
                  <div key={r.id} className="rounded-lg border border-slate-100 bg-white p-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-medium">{r.skill}</span>
                      {r.must_have && <Badge variant="outline" className="border-amber-300 text-[10px] text-amber-700">must-have</Badge>}
                      <Badge variant="secondary" className={`text-[10px] ${levelColor(r.level)}`}>{r.level} ({r.evidence_score.toFixed(2)})</Badge>
                      {r.verdict && <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${verdictColor(r.verdict)}`}>{r.verdict}</span>}
                      <span className="text-[10px] text-slate-400">
                        {r.category_label}
                        {r.exact > 0 && ` | exact match in ${r.exact_source}`}
                        {r.mentions > 0 && ` | ${r.mentions} mention${r.mentions > 1 ? "s" : ""}`}
                      </span>
                    </div>
                    {r.snippets.length > 0 && (
                      <ul className="mt-1.5 space-y-1">
                        {r.snippets.slice(0, 2).map((s, i) => (
                          <li key={i} className="flex gap-1.5 text-xs italic leading-snug text-slate-500">
                            <FileText className="mt-0.5 h-3 w-3 shrink-0" /> &ldquo;{s}&rdquo;
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <Separator />
            <div className="grid gap-2 text-xs sm:grid-cols-2">
              <div className="rounded-lg border border-slate-100 p-2.5">
                <p className="mb-1 flex items-center gap-1.5 font-semibold"><GitCompareArrows className="h-3.5 w-3.5 text-emerald-700" /> Shortlist decision (choice)</p>
                <p className="text-muted-foreground">
                  decision: <span className="font-mono">{c.choice.decision}</span> at confidence {c.choice.confidence.toFixed(2)}
                  {c.choice.escalate && ` - below floor ${c.choice.floor?.toFixed(2) ?? "0.73"}, in review band`}
                </p>
              </div>
              <div className="rounded-lg border border-slate-100 p-2.5">
                <p className="mb-1 flex items-center gap-1.5 font-semibold"><FileText className="h-3.5 w-3.5 text-emerald-700" /> Files</p>
                {c.files.map((f) => (
                  <p key={f.rel_path} className="font-mono text-muted-foreground">
                    {f.name}: {f.chars} chars{f.short_document ? " (short)" : ""}{!f.readable ? " (unreadable)" : ""}
                  </p>
                ))}
              </div>
            </div>

            <Separator />
            <div className="rounded-lg border border-emerald-900/10 p-3">
              <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
                <Signature className="h-4 w-4 text-emerald-700" /> Recruiter sign-off (GDPR audit trail)
              </p>
              <div className="flex flex-wrap items-end gap-2">
                <div className="space-y-1">
                  <Label htmlFor="reviewer" className="text-xs">Reviewer</Label>
                  <Input id="reviewer" value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="Your name" className="h-8 w-40 text-xs" />
                </div>
                <Button size="sm" onClick={() => signOff("endorse")} className="gap-1 bg-emerald-700 hover:bg-emerald-800">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Endorse
                </Button>
                <Button size="sm" variant="outline" onClick={() => signOff("reject")} className="gap-1 text-rose-700">
                  Reject
                </Button>
              </div>
              {signMsg && <p className="mt-2 text-xs text-emerald-800">{signMsg}</p>}
            </div>
          </div>
        </ScrollArea>
        <div className="flex justify-end">
          <Button variant="outline" size="sm" onClick={onClose}>Close</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
