"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { api, CATEGORY_KEYS, CATEGORY_LABELS, emptyCategories, fromEngineProfile, toEngineProfile, type CategoryKey, type JobProfile, type ProfileCategories } from "@/lib/attune";
import {
  Award,
  BookOpenCheck,
  Building2,
  ChevronDown,
  FileSignature,
  GraduationCap,
  HeartPulse,
  Languages as LangIcon,
  Plus,
  Save,
  Sparkles,
  Trash2,
  Wrench,
} from "lucide-react";

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  soft_skills: <HeartPulse className="h-4 w-4 text-rose-600" />,
  technical_skills: <Wrench className="h-4 w-4 text-emerald-700" />,
  languages: <LangIcon className="h-4 w-4 text-teal-700" />,
  degrees: <GraduationCap className="h-4 w-4 text-amber-700" />,
  certifications: <Award className="h-4 w-4 text-lime-700" />,
  bootcamps: <BookOpenCheck className="h-4 w-4 text-cyan-700" />,
};

// stable ids for editable rows: index keys break focus/slider state when a
// middle row is deleted
let skillRowSeq = 0;

function newSkill() {
  skillRowSeq += 1;
  return { id: skillRowSeq, skill: "", weight: 1, mustHave: false, aliases: "" };
}

export default function JobProfileEditor({
  profile,
  onChange,
  onNext,
  starting = false,
}: {
  profile: JobProfile;
  onChange: (p: JobProfile) => void;
  onNext: () => void;
  starting?: boolean;
}) {
  const [open, setOpen] = useState<Record<string, boolean>>({ technical_skills: true });
  const [templates, setTemplates] = useState<{ name: string; title: string }[]>([]);
  const [tplOpen, setTplOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [tplError, setTplError] = useState<string | null>(null);

  // fetch templates only when the picker dialog opens (not on every mount/close)
  useEffect(() => {
    if (!tplOpen) return;
    api<{ templates: { name: string; title: string }[] }>("/api/template")
      .then((d) => {
        setTemplates(d.templates);
        setTplError(null); // clear a previous failure once a fetch succeeds
      })
      .catch((e) => setTplError(e instanceof Error ? e.message : "Could not load templates"));
  }, [tplOpen]);

  function setCategory(key: CategoryKey, rows: ProfileCategories[CategoryKey]) {
    onChange({ ...profile, categories: { ...profile.categories, [key]: rows } });
  }

  async function loadTemplate(name: string) {
    try {
      const d = await api<{ profile: Record<string, unknown> }>(`/api/template?name=${encodeURIComponent(name)}`);
      const raw = d.profile as { profileName?: string };
      const converted = fromEngineProfile(d.profile as Parameters<typeof fromEngineProfile>[0]);
      converted.profileName = raw.profileName ?? name;
      onChange(converted);
      setTplOpen(false);
      setMsg(`Loaded template "${name}".`);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Load failed");
    }
  }

  async function saveTemplate() {
    if (!saveName.trim()) return;
    try {
      const engineProfile = toEngineProfile({ ...profile, profileName: saveName.trim() }, {}, true);
      await api("/api/template", { method: "POST", body: JSON.stringify({ action: "save", name: saveName.trim(), profile: engineProfile }) });
      setMsg(`Template "${saveName.trim()}" saved for reuse.`);
      setSaveName("");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Save failed");
    }
  }

  async function loadExample() {
    await loadTemplate("example-senior-data-engineer");
  }

  const totalSkills = CATEGORY_KEYS.reduce((n, k) => n + profile.categories[k].length, 0);
  const totalMust = CATEGORY_KEYS.reduce((n, k) => n + profile.categories[k].filter((r) => r.mustHave).length, 0);

  return (
    <div className="space-y-5">
      <Card className="border-emerald-900/10 shadow-sm">
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Building2 className="h-5 w-5 text-emerald-700" />
                Company &amp; job profile
              </CardTitle>
              <CardDescription>
                Who is hiring, what the role is, and which skills matter. Each skill gets its own field so the full requirements list fits.
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={loadExample} className="gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-emerald-700" /> Load example
              </Button>
              <Button variant="outline" size="sm" onClick={() => { setTplError(null); setTplOpen(true); }} className="gap-1.5">
                <FileSignature className="h-3.5 w-3.5" /> Templates
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="cname">Company name</Label>
            <Input id="cname" value={profile.company.name} onChange={(e) => onChange({ ...profile, company: { ...profile.company, name: e.target.value } })} placeholder="NovaGrid Energy" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="jtitle">Job title</Label>
            <Input id="jtitle" value={profile.job.title} onChange={(e) => onChange({ ...profile, job: { ...profile.job, title: e.target.value } })} placeholder="Senior Data Engineer" />
          </div>
          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="csummary">Company summary</Label>
            <Textarea id="csummary" rows={2} value={profile.company.summary} onChange={(e) => onChange({ ...profile, company: { ...profile.company, summary: e.target.value } })} placeholder="What the company does, in two sentences." />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cvalues">Company values (one per line or comma-separated)</Label>
            <Textarea id="cvalues" rows={3} value={profile.company.valuesText} onChange={(e) => onChange({ ...profile, company: { ...profile.company, valuesText: e.target.value } })} placeholder={"safety first\nreliable engineering\nopen communication"} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="jdesc">Job description</Label>
            <Textarea id="jdesc" rows={3} value={profile.job.description} onChange={(e) => onChange({ ...profile, job: { ...profile.job, description: e.target.value } })} placeholder="What the person will do." />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 lg:grid-cols-2">
        {CATEGORY_KEYS.map((key) => {
          const rows = profile.categories[key];
          const mustCount = rows.filter((r) => r.mustHave).length;
          return (
            <Collapsible
              key={key}
              open={open[key]}
              onOpenChange={(v) => setOpen({ ...open, [key]: v })}
              className="rounded-xl border border-slate-200 bg-white shadow-sm"
            >
              <CollapsibleTrigger className="flex w-full items-center gap-2 p-4 text-left hover:bg-slate-50 rounded-xl">
                {CATEGORY_ICONS[key]}
                <span className="flex-1 text-sm font-semibold">{CATEGORY_LABELS[key]}</span>
                <Badge variant="secondary" className="bg-emerald-50 text-emerald-800">{rows.length} skills</Badge>
                {mustCount > 0 && <Badge variant="outline" className="border-amber-300 text-amber-700">{mustCount} must-have</Badge>}
                <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform ${open[key] ? "rotate-180" : ""}`} />
              </CollapsibleTrigger>
              <CollapsibleContent className="px-4 pb-4">
                <div className="space-y-3">
                  {rows.length === 0 && <p className="text-xs text-muted-foreground">No skills yet - add the first one.</p>}
                  {rows.map((row, idx) => (
                    <div key={row.id ?? `idx-${idx}`} className="rounded-lg border border-slate-100 bg-slate-50/60 p-3">
                      <div className="flex items-center gap-2">
                        <Input
                          value={row.skill}
                          placeholder="Skill, e.g. Apache Airflow"
                          onChange={(e) => {
                            const next = [...rows];
                            next[idx] = { ...row, skill: e.target.value };
                            setCategory(key, next);
                          }}
                          className="h-8 text-sm"
                        />
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 shrink-0 text-slate-400 hover:text-rose-600"
                          onClick={() => setCategory(key, rows.filter((_, i) => i !== idx))}
                          aria-label="Remove skill"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
                        <div className="flex min-w-[150px] flex-1 items-center gap-2">
                          <span className="w-14 text-xs text-muted-foreground">Weight</span>
                          <Slider
                            value={[row.weight]}
                            min={0.5}
                            max={3}
                            step={0.5}
                            onValueChange={(v) => {
                              const next = [...rows];
                              next[idx] = { ...row, weight: v[0] };
                              setCategory(key, next);
                            }}
                            className="w-24"
                          />
                          <Badge variant="secondary" className="text-xs">{row.weight}x</Badge>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <Switch
                            checked={row.mustHave}
                            onCheckedChange={(v) => {
                              const next = [...rows];
                              next[idx] = { ...row, mustHave: v };
                              setCategory(key, next);
                            }}
                            aria-label="Must-have"
                          />
                          <span className="text-xs text-muted-foreground">Must-have</span>
                        </div>
                      </div>
                      <Input
                        value={row.aliases}
                        placeholder="Aliases, comma-separated (e.g. airflow, dags)"
                        onChange={(e) => {
                          const next = [...rows];
                          next[idx] = { ...row, aliases: e.target.value };
                          setCategory(key, next);
                        }}
                        className="mt-2 h-7 border-dashed text-xs"
                      />
                    </div>
                  ))}
                  <Button variant="outline" size="sm" className="w-full gap-1.5 border-dashed" onClick={() => setCategory(key, [...rows, newSkill()])}>
                    <Plus className="h-3.5 w-3.5" /> Add skill
                  </Button>
                </div>
              </CollapsibleContent>
            </Collapsible>
          );
        })}
      </div>

      {msg && <p className="text-xs text-emerald-800">{msg}</p>}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-900/10 bg-white p-4 shadow-sm">
        <div className="text-sm text-muted-foreground">
          <span className="font-semibold text-slate-900">{totalSkills}</span> skills across 6 categories,{" "}
          <span className="font-semibold text-amber-700">{totalMust}</span> marked must-have.
          {!profile.job.title.trim() && <span className="text-amber-700"> - add a job title first.</span>}
          {profile.job.title.trim() && totalSkills === 0 && <span className="text-amber-700"> - add at least one skill.</span>}
        </div>
        <Button onClick={onNext} disabled={starting || !profile.job.title.trim() || totalSkills === 0} className="gap-1.5 bg-emerald-700 hover:bg-emerald-800">
          {starting ? "Starting..." : (<>Start screening run <Save className="h-4 w-4" /></>)}
        </Button>
      </div>

      <Dialog open={tplOpen} onOpenChange={setTplOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base">Profile templates</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {/* save/load feedback lives INSIDE the dialog so it is visible while
                the modal is open */}
            {msg && <p className="text-xs text-emerald-800">{msg}</p>}
            {tplError && <p className="text-xs text-rose-700">{tplError}</p>}
            <div className="space-y-1.5">
              <Label htmlFor="tplname">Save current profile as</Label>
              <div className="flex gap-2">
                <Input id="tplname" value={saveName} onChange={(e) => setSaveName(e.target.value)} placeholder="e.g. Senior DE spring" />
                <Button size="sm" onClick={saveTemplate} disabled={!saveName.trim()} className="bg-emerald-700 hover:bg-emerald-800">
                  Save
                </Button>
              </div>
            </div>
            <Select onValueChange={(v) => loadTemplate(v)}>
              <SelectTrigger>
                <SelectValue placeholder="Load a saved template..." />
              </SelectTrigger>
              <SelectContent>
                {templates.length === 0 && <SelectItem value="none" disabled>No templates yet</SelectItem>}
                {templates.map((t) => (
                  <SelectItem key={t.name} value={t.name}>
                    {t.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
