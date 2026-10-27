"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useMemo } from "react";
import type { CandidateResult, ComparisonBlock, RunResults } from "@/lib/attune";
import { AlertTriangle, Crown, GitCompareArrows, Layers, Scale, Sparkles, Swords, TrendingUp, Users } from "lucide-react";

const VERDICT_STYLES: Record<string, { label: string; cls: string }> = {
  strong_front_runner: { label: "Strong front-runner - proceed to shortlist / offer", cls: "border-emerald-300 bg-emerald-50 text-emerald-900" },
  proceed_to_interview: { label: "Proceed to interview", cls: "border-teal-300 bg-teal-50 text-teal-900" },
  hold_review: { label: "Hold - manual review before any decision", cls: "border-amber-300 bg-amber-50 text-amber-900" },
  blocked_manual_review: { label: "Blocked - manual review required (unreadable documents)", cls: "border-rose-300 bg-rose-50 text-rose-900" },
  no_strong_match_this_round: { label: "No strong match this round", cls: "border-rose-300 bg-rose-50 text-rose-900" },
};

function heat(score: number | null | undefined) {
  if (score == null) return "bg-white text-slate-300";
  if (score >= 0.8) return "bg-emerald-100 text-emerald-900 font-semibold";
  if (score >= 0.4) return "bg-amber-100 text-amber-900";
  return "bg-rose-50 text-rose-700";
}

export default function PositionReport({ results }: { results: RunResults }) {
  // hooks must run unconditionally: keep useMemo above the old-run early return
  const byRef: Record<string, CandidateResult> = useMemo(
    () => Object.fromEntries(results.candidates.map((c) => [c.candidate_ref, c])),
    [results.candidates],
  );
  const comp: ComparisonBlock | undefined = results.comparison;
  if (!comp?.verdict) {
    return (
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="p-6 text-sm text-muted-foreground">
          This run was produced by an older engine version without the comparison block. Start a new run to get the position verdict, comparison matrices and per-applicant dossiers.
        </CardContent>
      </Card>
    );
  }
  const v = comp.verdict;
  const verdict = VERDICT_STYLES[v.recommendation] ?? { label: "Review recommended", cls: "border-amber-300 bg-amber-50 text-amber-900" };
  const topPick = v.top_pick_ref ? byRef[v.top_pick_ref] : undefined;
  const runnerUp = v.runner_up_ref ? byRef[v.runner_up_ref] : undefined;
  const matrix = comp.skill_coverage_matrix;

  return (
    <div className="space-y-4">
      {/* verdict banner */}
      <Card className={`border shadow-sm ${verdict.cls}`}>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Crown className="h-5 w-5" /> Position verdict
          </CardTitle>
          <CardDescription className={verdict.cls.includes("emerald") ? "text-emerald-800" : "text-current"}>
            Deterministic recommendation derived from the scored cohort - human sign-off still required.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-base font-bold">{verdict.label}</p>
          <p className="text-sm leading-relaxed">{v.rationale}</p>
          {v.next_steps && v.next_steps.length > 0 && (
            <div className="rounded-lg border border-white/40 bg-white/50 p-2.5">
              <p className="text-[10px] font-bold uppercase tracking-wide opacity-60">Recommended next steps</p>
              <ul className="mt-1 list-inside list-disc space-y-0.5 text-sm">
                {v.next_steps.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          )}
          {v.order_note && (
            <p className="flex items-center gap-1.5 text-xs opacity-80">
              <Scale className="h-3.5 w-3.5" /> {v.order_note}
            </p>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* category leaders */}
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="h-4 w-4 text-emerald-700" /> Category leaders
            </CardTitle>
            <CardDescription>Who leads each requirement category across the whole field.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1.5">
            {comp.category_leaders.map((l) => (
              <div key={l.category} className="flex items-center gap-2 text-sm">
                <span className="w-40 shrink-0 truncate text-muted-foreground">{l.label}</span>
                <Badge variant="outline" className="border-emerald-200 bg-emerald-50 font-mono text-[11px] text-emerald-800">
                  {byRef[l.leader_ref]?.folder_name ?? l.leader_ref}
                </Badge>
                <span className="ml-auto text-xs font-semibold tabular-nums">{Math.round(l.avg * 100)}%</span>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* differentiators */}
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <GitCompareArrows className="h-4 w-4 text-emerald-700" /> Key differentiators
            </CardTitle>
            <CardDescription>Skills where one applicant clearly separates from the cohort mean.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1.5">
            {comp.differentiators.length === 0 && (
              <p className="text-sm text-muted-foreground">No strong separation signals in this cohort.</p>
            )}
            {comp.differentiators.map((d) => (
              <div key={d.skill} className="flex items-center gap-2 text-sm">
                <span className="min-w-0 flex-1 truncate">{d.skill}</span>
                <Badge variant="outline" className="border-emerald-200 bg-emerald-50 font-mono text-[10px] text-emerald-800">
                  {byRef[d.leader_ref]?.folder_name ?? d.leader_ref}
                </Badge>
                <span className="w-28 text-right text-xs tabular-nums text-muted-foreground">
                  {d.leader_score.toFixed(2)} vs mean {d.cohort_mean.toFixed(2)}
                </span>
                <span className="w-12 text-right text-xs font-bold tabular-nums text-emerald-700">+{d.edge.toFixed(2)}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      {/* bench strength + market gaps */}
      {(comp.bench?.length || comp.market_gaps?.length) ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="border-slate-200 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <Layers className="h-4 w-4 text-emerald-700" /> Bench strength by category
              </CardTitle>
              <CardDescription>How deep the applicant pool runs per requirement category.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-1.5">
              {(comp.bench ?? []).map((b) => {
                const read = b.strong >= 3 ? "deep bench" : b.strong >= 2 ? "solid depth" : b.strong === 1 ? "single point of failure" : "no strong applicants";
                return (
                  <div key={b.category} className="flex items-center gap-2 text-sm">
                    <span className="w-40 shrink-0 truncate text-muted-foreground">{b.label}</span>
                    <span className="flex items-center gap-1">
                      <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[11px] font-bold tabular-nums text-emerald-800">{b.strong} strong</span>
                      <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] tabular-nums text-amber-800">{b.capable} capable</span>
                      <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[11px] tabular-nums text-rose-700">{b.thin} thin</span>
                    </span>
                    <span className="ml-auto text-right text-[11px] italic text-muted-foreground">{read}</span>
                  </div>
                );
              })}
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <AlertTriangle className="h-4 w-4 text-amber-600" /> Market gaps &amp; unique edges
              </CardTitle>
              <CardDescription>Requirements the whole cohort misses - and skills only one applicant brings.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {(comp.market_gaps ?? []).length === 0 ? (
                <p className="text-sm text-muted-foreground">No market gaps - every requirement has at least one applicant with solid evidence.</p>
              ) : (
                (comp.market_gaps ?? []).map((g) => (
                  <div key={g.skill} className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs">
                    <span className="min-w-0 flex-1 truncate">{g.skill}{g.must_have && <span className="ml-1 font-bold text-amber-700">(must-have)</span>}</span>
                    <span className="tabular-nums text-amber-800">best {g.best_score.toFixed(2)}</span>
                    <span className="text-amber-700/70">{g.n_with_evidence}/{results.candidates.length} w/ evidence</span>
                  </div>
                ))
              )}
              {(comp.unique_strengths ?? []).length > 0 && (
                <div className="space-y-1 pt-1">
                  {(comp.unique_strengths ?? []).map((u) => (
                    <p key={u.ref} className="flex items-start gap-1.5 text-xs text-emerald-900">
                      <Sparkles className="mt-0.5 h-3 w-3 shrink-0 text-amber-500" />
                      <span><b className="font-mono">{byRef[u.ref]?.folder_name ?? u.ref}</b> is the only applicant with strong evidence for: {u.skills.join(", ")}</span>
                    </p>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {/* head to head */}
      {comp.head_to_head && topPick && runnerUp && (
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Swords className="h-4 w-4 text-emerald-700" /> Head-to-head: {topPick.folder_name} vs {runnerUp.folder_name}
            </CardTitle>
            <CardDescription>
              {comp.head_to_head.overall.top_pick.toFixed(1)} vs {comp.head_to_head.overall.runner_up.toFixed(1)} points (gap {comp.head_to_head.overall.gap.toFixed(1)}).
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="grid gap-1.5 sm:grid-cols-2">
              {comp.head_to_head.categories.map((c) => (
                <div key={c.category} className="flex items-center gap-2 rounded-lg border border-slate-100 bg-white px-2.5 py-1.5 text-xs">
                  <span className="min-w-0 flex-1 truncate">{c.label}</span>
                  <span className={c.winner === "top_pick" ? "font-bold tabular-nums text-emerald-700" : "tabular-nums text-slate-500"}>
                    {c.top_pick == null ? "-" : `${Math.round(c.top_pick * 100)}%`}
                  </span>
                  <span className="text-slate-300">vs</span>
                  <span className={c.winner === "runner_up" ? "font-bold tabular-nums text-teal-700" : "tabular-nums text-slate-500"}>
                    {c.runner_up == null ? "-" : `${Math.round(c.runner_up * 100)}%`}
                  </span>
                </div>
              ))}
            </div>
            {comp.head_to_head.runner_up_advantages.length > 0 && (
              <p className="flex items-start gap-1.5 rounded-lg bg-amber-50 p-2.5 text-xs text-amber-900">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>
                  Where the runner-up is stronger (interview focus):{" "}
                  {comp.head_to_head.runner_up_advantages.map((a) => `${a.skill} (${a.runner_up.toFixed(2)} vs ${a.top_pick.toFixed(2)})`).join("; ")}
                </span>
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* skill coverage matrix */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Skill coverage matrix (evidence 0-1, best to worst)</CardTitle>
          <CardDescription>Requirements as rows, applicants as columns in ranking order. Green &ge; 0.80, amber &ge; 0.40, red below. MH = must-have.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-separate border-spacing-0 text-xs">
            <thead>
              <tr>
                <th className="sticky left-0 z-10 bg-white px-2 py-1.5 text-left font-semibold">Requirement</th>
                <th className="px-1 py-1.5 text-center font-semibold">MH</th>
                {comp.candidates_order.map((ref) => (
                  <th key={ref} className="px-1 py-1.5 text-center font-mono text-[10px] font-semibold">
                    {byRef[ref]?.folder_name ?? ref}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.map((row) => (
                <tr key={row.id}>
                  <td className="sticky left-0 z-10 max-w-[220px] truncate bg-white px-2 py-1">
                    {row.skill}
                  </td>
                  <td className="px-1 py-1 text-center text-[10px] text-slate-400">{row.must_have ? "Y" : "-"}</td>
                  {comp.candidates_order.map((ref) => {
                    const s = row.scores[ref];
                    return (
                      <td key={ref} className={`px-1 py-1 text-center tabular-nums ${heat(s)}`}>
                        {s == null ? "-" : s.toFixed(2)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
      {/* talent pool insights */}
      {results.statistics?.talent_pool && (
        <Card className="border-slate-200 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Users className="h-4 w-4 text-emerald-700" /> Talent pool insights
            </CardTitle>
            <CardDescription>What the applicant pool for this position looks like as a whole.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(results.statistics.talent_pool.common_skills ?? []).length > 0 && (
              <div className="space-y-1.5">
                <p className="text-xs font-semibold text-slate-700">Most common skills across the cohort</p>
                {results.statistics.talent_pool.common_skills.map((s) => (
                  <div key={s.skill} className="flex items-center gap-2 text-xs">
                    <span className="w-40 shrink-0 truncate">{s.skill}</span>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full rounded-full bg-emerald-600/70" style={{ width: `${s.pct}%` }} />
                    </div>
                    <span className="w-16 text-right tabular-nums text-muted-foreground">{s.pct}% ({s.count})</span>
                  </div>
                ))}
              </div>
            )}
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              {Object.entries(results.statistics.talent_pool.education_distribution ?? {}).map(([k, n]) => (
                <span key={k}>highest education <b className="text-slate-700">{k}</b>: {n}</span>
              ))}
              {(results.statistics.talent_pool.languages_distribution ?? []).slice(0, 4).map((l) => (
                <span key={l.language}>{l.language}: <b className="text-slate-700">{l.count}</b></span>
              ))}
              {results.statistics.talent_pool.median_experience_years != null && (
                <span>median experience <b className="text-slate-700">{results.statistics.talent_pool.median_experience_years.toFixed(1)} yrs</b></span>
              )}
              <span>avg skills detected <b className="text-slate-700">{results.statistics.talent_pool.avg_skills_per_candidate.toFixed(1)}</b></span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
