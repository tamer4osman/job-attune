// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
//
// Shared client helpers for the Job Attune UI - the vanilla-JS port of the
// old src/lib/attune.ts (API wrapper, profile conversion, formatting).

export const CATEGORY_KEYS = [
  "soft_skills",
  "technical_skills",
  "languages",
  "degrees",
  "certifications",
  "bootcamps",
];

export const CATEGORY_LABELS = {
  soft_skills: "Soft Skills",
  technical_skills: "Technical Skills",
  languages: "Languages",
  degrees: "University Degrees",
  certifications: "Certifications",
  bootcamps: "Bootcamps",
};

const API_CLIENT_HEADER = "X-Attune-Client";

/** fetch wrapper with the loopback-guard header (see server.py). */
export async function api(url, init = {}) {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      // loopback guard: requests without this header are rejected, which
      // also blocks cross-site no-cors POSTs
      [API_CLIENT_HEADER]: "attune-ui",
      ...(init.headers ?? {}),
    },
    signal: init.signal,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error ?? `Request failed (${res.status})`);
  }
  // fall back to an error (not a silent {}) when a 2xx body fails to parse
  return res.json().catch(() => {
    throw new Error("Malformed response body");
  });
}

/**
 * Download a generated PDF through the guarded API and hand it to the
 * browser as a blob. The old Next.js UI used a plain <a href download>,
 * which the loopback middleware rejected (anchors cannot send custom
 * headers) - fetching with the client header fixes that.
 */
export async function downloadReport(runId, file) {
  const res = await fetch(
    `/api/report?run_id=${encodeURIComponent(runId)}&file=${encodeURIComponent(file)}`,
    { headers: { [API_CLIENT_HEADER]: "attune-ui" } },
  );
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error ?? `Download failed (${res.status})`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = file;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

function emptyCategories() {
  return {
    soft_skills: [],
    technical_skills: [],
    languages: [],
    degrees: [],
    certifications: [],
    bootcamps: [],
  };
}

export const EMPTY_PROFILE = () => ({
  profileName: "",
  company: { name: "", summary: "", valuesText: "" },
  job: { title: "", description: "" },
  categories: emptyCategories(),
});

/** UI-format -> engine-format (snake_case for the Python pipeline). */
export function toEngineProfile(profile, roleOverrides, pseudonymous) {
  const categories = {};
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
export function fromEngineProfile(raw) {
  const cats = raw.categories ?? {};
  const categories = emptyCategories();
  for (const key of CATEGORY_KEYS) {
    categories[key] = (cats[key] ?? []).map((r) => ({
      skill: r.skill ?? "",
      weight: r.weight ?? 1,
      mustHave: !!r.must_have,
      aliases: (r.aliases ?? []).join(", "),
    }));
  }
  const company = raw.company ?? {};
  const job = raw.job ?? {};
  return {
    profileName: raw.profile_name ?? "",
    company: {
      name: company.name ?? "",
      summary: company.summary ?? "",
      valuesText: company.values_text ?? "",
    },
    job: { title: job.title ?? "", description: job.description ?? "" },
    categories,
  };
}

export function fmtBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}