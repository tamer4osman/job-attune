// Shared types + client helpers for the Job Attune UI.

export const CATEGORY_KEYS = [
  "soft_skills",
  "technical_skills",
  "languages",
  "degrees",
  "certifications",
  "bootcamps",
] as const;

export type CategoryKey = (typeof CATEGORY_KEYS)[number];

export const CATEGORY_LABELS: Record<CategoryKey, string> = {
  soft_skills: "Soft Skills",
  technical_skills: "Technical Skills",
  languages: "Languages",
  degrees: "University Degrees",
  certifications: "Certifications",
  bootcamps: "Bootcamps",
};

export interface SkillReq {
  id?: number; // stable React key for editable rows (set by the profile editor)
  skill: string;
  weight: number;
  mustHave: boolean;
  aliases: string;
}

export type ProfileCategories = Record<CategoryKey, SkillReq[]>;

export interface JobProfile {
  profileName?: string;
  company: { name: string; summary: string; valuesText: string };
  job: { title: string; description: string };
  categories: ProfileCategories;
}

export function emptyCategories(): ProfileCategories {
  return {
    soft_skills: [],
    technical_skills: [],
    languages: [],
    degrees: [],
    certifications: [],
    bootcamps: [],
  };
}

/** Engine-format conversion (snake_case for the Python pipeline). */
export function toEngineProfile(profile: JobProfile, roleOverrides: Record<string, string>, pseudonymous: boolean) {
  const categories: Record<string, { skill: string; weight: number; must_have: boolean; aliases: string[] }[]> = {};
  for (const key of CATEGORY_KEYS) {
    categories[key] = profile.categories[key]
      .filter((r) => r.skill.trim())
      .map((r) => ({
        skill: r.skill.trim(),
        weight: r.weight,
        must_have: r.mustHave,
        aliases: r.aliases.split(",").map((a) => a.trim()).filter(Boolean),
      }));
  }
  return {
    profile_name: profile.profileName || "",
    company: {
      name: profile.company.name,
      summary: profile.company.summary,
      values_text: profile.company.valuesText,
    },
    job: profile.job,
    categories,
    // scoring weights are engine-owned config (profile.get("weights") with
    // defaults in aggregate_stage) - the UI must not pin them
    pseudonymous,
    role_overrides: roleOverrides,
  };
}

/** Engine-format -> UI format (templates + example). */
export function fromEngineProfile(raw: Record<string, unknown>): JobProfile {
  const cats = (raw.categories ?? {}) as Record<string, { skill: string; weight?: number; must_have?: boolean; aliases?: string[] }[]>;
  const categories = emptyCategories();
  for (const key of CATEGORY_KEYS) {
    categories[key] = (cats[key] ?? []).map((r) => ({
      skill: r.skill ?? "",
      weight: r.weight ?? 1,
      mustHave: !!r.must_have,
      aliases: (r.aliases ?? []).join(", "),
    }));
  }
  const company = (raw.company ?? {}) as { name?: string; summary?: string; values_text?: string };
  const job = (raw.job ?? {}) as { title?: string; description?: string };
  return {
    profileName: (raw.profile_name as string) ?? "",
    company: { name: company.name ?? "", summary: company.summary ?? "", valuesText: company.values_text ?? "" },
    job: { title: job.title ?? "", description: job.description ?? "" },
    categories,
  };
}

// ---------------- scan / run / results types ----------------

export interface ScanFile {
  name: string;
  relPath: string;
  role: "cv" | "cover" | "unclassified";
  sizeBytes: number;
}

export interface ScanCandidate {
  folder: string;
  files: ScanFile[];
  hasCv: boolean;
  hasCover: boolean;
}

export interface ScanResult {
  folder: string;
  candidates: ScanCandidate[];
  notes: (string | { folder: string; note: string })[];
}

export interface RequirementResult {
  id: string;
  category: string;
  category_label: string;
  skill: string;
  weight: number;
  must_have: boolean;
  aliases: string[];
  exact: number;
  exact_source: string | null;
  token_fraction: number;
  mentions: number;
  snippets: string[];
  extract_confidence: number;
  snippet_support: boolean;
  evidence_score: number;
  level: string;
  verdict?: string;
}

export interface CandidateResult {
  candidate_ref: string;
  folder_name: string;
  rank: number;
  files: { name: string; rel_path: string; role: string; size_bytes: number; sha256: string; pages: number; chars: number; method: string | null; error: string | null; readable: boolean; short_document?: boolean }[];
  noul_gates: { file: string; role: string; chars: number; confidence: number; floor: number; escalate: boolean; blocking: boolean; raw_unreadable: boolean; short_document?: boolean }[];
  requirements: RequirementResult[];
  categories: { category: string; label: string; avg: number; kernel_score_confidence: number; kernel_score_result: string | null; score_advisory: boolean }[];
  values_fit: number | null;
  values_per_phrase: { phrase: string; coverage: number }[];
  must_have_missing: string[];
  overall: number;
  band: string;
  choice: { decision: string; confidence: number; escalate: boolean; floor?: number };
  shortlisted: boolean;
  strengths: string[];
  gaps: string[];
  overall_assessment: string;
  escalation_count?: number;
  // v1.1.0 enrichment (optional: older runs predate these)
  profile_card?: ProfileCard;
  skills_inventory?: { skill: string; mentions: number }[];
  interview_prompts?: string[];
  cohort?: CohortStanding;
  // v1.2.0 review-readiness enrichment
  verdict_summary?: { met: number; partial: number; missing: number; must_have_met: number; must_have_total: number; completeness_pct: number };
  score_decomposition?: {
    weights: { categories_total: number; values_fit: number };
    contributions: { category: string; label: string; avg: number; points: number }[];
    values_fit_points: number;
    sum_points: number;
    cap_applied: boolean;
    note: string | null;
  };
  evidence_quality?: { avg_evidence: number; doc_backed: number; doc_backed_pct: number; low_confidence_extracts: number; requirements_total: number };
  tier?: string;
  review_note?: string;
}

export interface ProfileCard {
  experience_years: number | null;
  experience_basis: string;
  seniority_estimate: string;
  seniority_signal: string | null;
  education: { level: string; detail: string }[];
  languages: { language: string; level: string; band: string }[];
  certifications: string[];
  achievements: string[];
  career_timeline: { span: string; months: number }[];
  tenure?: { positions: number; avg_months: number; longest_months: number } | null;
  risk_flags: { flag: string; detail: string }[];
}

export interface CohortStanding {
  percentile_overall: number;
  delta_vs_mean: number;
  delta_vs_best: number;
  category_percentile: Record<string, number>;
  category_rank: Record<string, number>;
}

export interface ComparisonBlock {
  candidates_order: string[];
  category_leaders: { category: string; label: string; leader_ref: string; avg: number }[];
  skill_coverage_matrix: { id: string; skill: string; category: string; category_label: string; must_have: boolean; scores: Record<string, number | null> }[];
  differentiators: { skill: string; leader_ref: string; leader_score: number; cohort_mean: number; edge: number }[];
  market_gaps?: { skill: string; category_label: string; must_have: boolean; best_score: number; best_ref: string; n_with_evidence: number }[];
  bench?: { category: string; label: string; candidates: number; strong: number; capable: number; thin: number }[];
  unique_strengths?: { ref: string; skills: string[] }[];
  head_to_head: {
    top_pick_ref: string;
    runner_up_ref: string;
    overall: { top_pick: number; runner_up: number; gap: number };
    categories: { category: string; label: string; top_pick: number | null; runner_up: number | null; winner: string }[];
    runner_up_advantages: { skill: string; top_pick: number; runner_up: number }[];
  } | null;
  verdict: {
    recommendation: string;
    top_pick_ref: string;
    runner_up_ref: string | null;
    margin_to_runner_up: number | null;
    rationale: string;
    order_note: string | null;
    next_steps?: string[];
  } | null;
}

export interface ReviewItem {
  kind: string;
  primitive: string;
  candidate_ref: string | null;
  blocking: boolean;
  detail: string;
  confidence: number;
  floor: number;
}

export interface RunResults {
  run_id: string;
  created_at: string;
  engine_version: string;
  omnidecide_version: string;
  floors_data_version: string;
  profile: { title: string; company: string };
  candidates: CandidateResult[];
  ranking: string[];
  ranking_labels: string[];
  scan_notes: { folder: string; note: string }[];
  statistics: {
    candidates_total: number;
    readable_cv: number;
    with_cover_letter: number;
    must_have_complete: number;
    shortlisted: number;
    funnel: { stage: string; count: number }[];
    bands: Record<string, number>;
    score_histogram: { bucket: string; count: number }[];
    category_averages: Record<string, { label: string; avg: number | null }>;
    requirement_coverage: { skill: string; category: string; coverage_pct: number; n: number }[];
    average_overall: number;
    seniority_distribution?: Record<string, number>;
    average_experience_years?: number | null;
    candidates_with_risk_flags?: number;
    tiers?: { A: number; B: number; C: number };
    talent_pool?: {
      common_skills: { skill: string; count: number; pct: number }[];
      education_distribution: Record<string, number>;
      languages_distribution: { language: string; count: number }[];
      median_experience_years: number | null;
      avg_skills_per_candidate: number;
    };
  };
  review_queue: ReviewItem[];
  events: { compare: { pair: string[]; gap: number; decision: string; confidence: number; escalate: boolean; applied: boolean }[]; rank: Record<string, unknown> | null };
  comparison?: ComparisonBlock;
  audit?: {
    manifest: {
      engine_version: string;
      omnidecide_version: string;
      floors_data_version: string;
      floors_table: Record<string, number>;
      main_folder: string;
      profile_sha256: string;
      file_hashes: Record<string, Record<string, string>>;
      pseudonymous: boolean;
      determinism: { pass1_sha256: string; pass2_sha256: string; identical: boolean };
      elapsed_seconds: number;
      created_at: string;
    };
  };
  determinism: { pass1_sha256: string; pass2_sha256: string; identical: boolean };
}

export interface AuditDecision {
  at: string;
  action: string;
  candidate_ref: string | null;
  kind: string | null;
  decision: string | null;
  reviewer: string;
  note: string;
}

export interface ExportFile {
  kind: string;
  ref: string | null;
  file: string;
  sha256: string;
}

export const API_CLIENT_HEADER = "X-Attune-Client";

export async function api<T>(url: string, init?: RequestInit & { signal?: AbortSignal }): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      // loopback guard (see src/middleware.ts): requests without this header
      // are rejected, which also blocks cross-site no-cors POSTs
      [API_CLIENT_HEADER]: "attune-ui",
      ...(init?.headers ?? {}),
    },
    signal: init?.signal,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { error?: string }).error ?? `Request failed (${res.status})`);
  }
  // fall back to an error (not a silent {}) when a 2xx body fails to parse
  return res.json().catch(() => {
    throw new Error("Malformed response body");
  }) as Promise<T>;
}

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

