"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { RunResults } from "@/lib/attune";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BarChart3, Filter, Gauge, ShieldAlert } from "lucide-react";

const EMERALD = "#059669";
const TEAL = "#0d9488";
const AMBER = "#d97706";
const ROSE = "#e11d48";

const KIND_COLORS: Record<string, string> = {
  unreadable_document: ROSE,
  must_have_missing: AMBER,
  shortlist_band: AMBER,
  tie_unresolved: AMBER,
  rank_conflict: AMBER,
  score_advisory: TEAL,
  noul_kernel_advisory: TEAL,
  low_confidence_extraction: TEAL,
};

export default function OverviewCharts({ results }: { results: RunResults }) {
  const s = results.statistics;
  const funnel = s.funnel.map((f) => ({ ...f, fill: EMERALD }));
  const radar = Object.values(s.category_averages)
    .filter((c) => c.avg !== null)
    .map((c) => ({ category: c.label.replace("University ", "").replace(" Professional", "").replace("Training ", ""), avg: Math.round((c.avg ?? 0) * 100) }));
  const histogram = s.score_histogram;
  const escalations = Object.entries(
    results.review_queue.reduce<Record<string, number>>((acc, q) => {
      acc[q.kind] = (acc[q.kind] ?? 0) + 1;
      return acc;
    }, {}),
  ).map(([kind, count]) => ({ kind: kind.replace(/_/g, " "), count, color: KIND_COLORS[kind] ?? TEAL }));
  const coverage = s.requirement_coverage.slice(0, 18);

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Filter className="h-4 w-4 text-emerald-700" /> Screening funnel
          </CardTitle>
          <CardDescription>From applications received to shortlisted candidates.</CardDescription>
        </CardHeader>
        <CardContent className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={funnel} layout="vertical" margin={{ left: 8, right: 24 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="stage" width={150} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={22}>
                {funnel.map((f, i) => (
                  <Cell key={i} fill={EMERALD} fillOpacity={1 - i * 0.18} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Gauge className="h-4 w-4 text-emerald-700" /> Category averages
          </CardTitle>
          <CardDescription>Mean evidence strength per requirement category (0-100).</CardDescription>
        </CardHeader>
        <CardContent className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radar} outerRadius="78%">
              <PolarGrid stroke="#e2e8f0" />
              <PolarAngleAxis dataKey="category" tick={{ fontSize: 10 }} />
              <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 9 }} axisLine={false} />
              <Radar dataKey="avg" stroke={EMERALD} fill={EMERALD} fillOpacity={0.28} strokeWidth={2} />
              <Tooltip />
            </RadarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <BarChart3 className="h-4 w-4 text-emerald-700" /> Score distribution
          </CardTitle>
          <CardDescription>Candidates per overall score bucket.</CardDescription>
        </CardHeader>
        <CardContent className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={histogram} margin={{ left: -18, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="bucket" tick={{ fontSize: 10 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
              <Tooltip />
              <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                {histogram.map((_, i) => (
                  <Cell key={i} fill={i < 3 ? ROSE : i < 5 ? AMBER : EMERALD} fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldAlert className="h-4 w-4 text-emerald-700" /> Human review signals
          </CardTitle>
          <CardDescription>
            Calibrated floors catch uncertain machine decisions: {results.review_queue.filter((q) => q.blocking).length} blocking,{" "}
            {results.review_queue.filter((q) => !q.blocking).length} advisory.
          </CardDescription>
        </CardHeader>
        <CardContent className="h-52">
          {escalations.length === 0 ? (
            <p className="pt-8 text-center text-sm text-muted-foreground">No escalations - all decisions above their floors.</p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={escalations} layout="vertical" margin={{ left: 30, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e2e8f0" />
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="kind" width={160} tick={{ fontSize: 9.5 }} />
                <Tooltip />
                <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={16}>
                  {escalations.map((e, i) => (
                    <Cell key={i} fill={e.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm lg:col-span-2">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Requirement coverage (evidence found per requirement)</CardTitle>
          <CardDescription>Share of candidates with at least partial evidence for each skill - spot sourcing gaps at a glance.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {coverage.map((r) => {
              const pct = r.coverage_pct;
              const tone = pct >= 60 ? "bg-emerald-600" : pct >= 30 ? "bg-amber-500" : pct > 0 ? "bg-orange-400" : "bg-rose-500";
              return (
                <div key={r.skill} className="flex min-w-[150px] flex-1 items-center gap-2 rounded-lg border border-slate-100 px-2.5 py-2">
                  <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${tone}`} />
                  <span className="min-w-0 flex-1 truncate text-xs font-medium">{r.skill}</span>
                  <span className="text-xs tabular-nums text-muted-foreground">{pct}%</span>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
