"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { CandidateResult, RunResults } from "@/lib/attune";
import { CandidateDetailDialog } from "./candidate-detail";
import { useMemo, useState } from "react";
import { Crown, ListOrdered, UserRound } from "lucide-react";

const BAND_STYLES: Record<string, string> = {
  strong: "bg-emerald-100 text-emerald-800 border-emerald-200",
  good: "bg-teal-100 text-teal-800 border-teal-200",
  potential: "bg-amber-100 text-amber-800 border-amber-200",
  weak: "bg-rose-50 text-rose-700 border-rose-200",
};

const RANK_COLORS = ["#ca8a04", "#94a3b8", "#b45309", "#475569", "#475569"];

function rankBadge(rank: number) {
  const style =
    rank <= 3
      ? { backgroundColor: RANK_COLORS[rank - 1], color: "white" }
      : { backgroundColor: "#f1f5f9", color: "#334155" };
  return (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold" style={style}>
      {rank}
    </span>
  );
}

export function ScoreBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-gradient-to-r from-emerald-600 to-teal-500"
          style={{ width: `${Math.min(100, value)}%` }}
        />
      </div>
      <span className="w-12 text-right text-xs font-semibold tabular-nums">{value.toFixed(1)}</span>
    </div>
  );
}

export default function RankingBoard({ results }: { results: RunResults }) {
  const [selected, setSelected] = useState<CandidateResult | null>(null);
  const byRef = useMemo(() => Object.fromEntries(results.candidates.map((c) => [c.candidate_ref, c])), [results.candidates]);
  const { ordered, dropped } = useMemo(() => {
    const list: CandidateResult[] = [];
    let missing = 0;
    for (const ref of results.ranking) {
      const c = byRef[ref];
      if (c) list.push(c);
      else missing += 1; // corrupt/partial run: never silently hide the gap
    }
    return { ordered: list, dropped: missing };
  }, [results.ranking, byRef]);
  const labelFor = (c: CandidateResult) => c.folder_name;

  return (
    <div className="space-y-4">
      <Card className="border-emerald-900/10 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <ListOrdered className="h-5 w-5 text-emerald-700" />
            Ranking - best candidates first
          </CardTitle>
          <CardDescription>
            Descending by overall evidence score. Near-ties were checked with the compare primitive; the rank primitive validated the order.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {dropped > 0 && (
            <p className="mb-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              Warning: {dropped} ranked reference{dropped === 1 ? "" : "s"} missing from the candidate list - this run may be partial.
            </p>
          )}
          <div className="space-y-2">
            {ordered.map((c, i) => {
              const prev = i > 0 ? ordered[i - 1].overall : 999;
              const nearTie = prev - c.overall < 2.0 && i > 0;
              return (
                <button
                  key={c.candidate_ref}
                  onClick={() => setSelected(c)}
                  className="flex w-full items-center gap-3 rounded-xl border border-slate-200 bg-white p-3 text-left transition hover:border-emerald-300 hover:shadow-sm"
                >
                  {rankBadge(c.rank)}
                  {c.rank === 1 && <Crown className="h-4 w-4 text-amber-500" />}
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="truncate text-sm font-semibold">{labelFor(c)}</span>
                      <Badge variant="outline" className={`text-[11px] ${BAND_STYLES[c.band] ?? ""}`}>
                        {c.band}
                      </Badge>
                      {c.shortlisted && (
                        <Badge className="bg-emerald-700 text-[11px] text-white hover:bg-emerald-800">shortlisted</Badge>
                      )}
                      {c.must_have_missing.length > 0 && (
                        <Badge variant="outline" className="border-rose-200 bg-rose-50 text-[11px] text-rose-700">
                          gaps: {c.must_have_missing.length}
                        </Badge>
                      )}
                      {c.noul_gates.some((g) => g.blocking) && (
                        <Badge variant="outline" className="border-rose-300 bg-rose-50 text-[11px] text-rose-700">
                          unreadable - review
                        </Badge>
                      )}
                      {nearTie && (
                        <Badge variant="outline" className="text-[11px] text-slate-500">
                          near-tie
                        </Badge>
                      )}
                    </div>
                    <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">
                      {c.strengths.length > 0 && `Strengths: ${c.strengths.join(", ")}`}
                      {c.must_have_missing.length > 0 && ` | Missing must-haves: ${c.must_have_missing.join(", ")}`}
                      {c.profile_card?.seniority_estimate && c.profile_card.seniority_estimate !== "unknown" && ` | ${c.profile_card.seniority_estimate}${c.profile_card.experience_years != null ? ` (~${c.profile_card.experience_years.toFixed(0)} yrs)` : ""}`}
                      {c.cohort && ` | pctile ${c.cohort.percentile_overall.toFixed(0)}`}
                    </p>
                  </div>
                  <ScoreBar value={c.overall} />
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>
      <CandidateDetailDialog key={selected?.candidate_ref ?? "none"} candidate={selected} results={results} onClose={() => setSelected(null)} />
    </div>
  );
}

export function CandidateCards({ results }: { results: RunResults }) {
  const [selected, setSelected] = useState<CandidateResult | null>(null);
  const byRef = useMemo(() => Object.fromEntries(results.candidates.map((c) => [c.candidate_ref, c])), [results.candidates]);
  const ordered = useMemo(() => results.ranking.map((r) => byRef[r]).filter((c): c is CandidateResult => Boolean(c)), [results.ranking, byRef]);
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {ordered.map((c) => (
          <button
            key={c.candidate_ref}
            onClick={() => setSelected(c)}
            className="rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:border-emerald-300 hover:shadow"
          >
            <div className="flex items-center gap-2">
              <UserRound className="h-4 w-4 text-slate-500" />
              <span className="min-w-0 flex-1 truncate text-sm font-semibold">{c.folder_name}</span>
              <Badge variant="outline" className={`text-[11px] ${BAND_STYLES[c.band] ?? ""}`}>{c.band}</Badge>
            </div>
            <p className="mt-2 line-clamp-3 min-h-[48px] text-xs leading-relaxed text-muted-foreground">
              {c.overall_assessment}
            </p>
            <div className="mt-3">
              <ScoreBar value={c.overall} />
            </div>
          </button>
        ))}
      </div>
      <CandidateDetailDialog key={selected?.candidate_ref ?? "none-cards"} candidate={selected} results={results} onClose={() => setSelected(null)} />
    </div>
  );
}

export function StatCards({ results }: { results: RunResults }) {
  const s = results.statistics;
  const items = [
    { label: "Candidates", value: s.candidates_total },
    { label: "Readable CVs", value: s.readable_cv },
    { label: "Must-have complete", value: s.must_have_complete },
    { label: "Shortlisted", value: s.shortlisted },
    { label: "Avg overall", value: s.average_overall.toFixed(1) },
    { label: "Review items", value: results.review_queue.length },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {items.map((it) => (
        <Card key={it.label} className="border-slate-200 shadow-sm">
          <CardContent className="p-4">
            <p className="text-2xl font-bold tabular-nums text-slate-900">{it.value}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{it.label}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
