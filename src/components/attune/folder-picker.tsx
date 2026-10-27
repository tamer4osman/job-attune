"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { api, fmtBytes, type ScanResult } from "@/lib/attune";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  FileText,
  Folder,
  FolderOpen,
  FolderUp,
  Loader2,
  Search,
  ShieldCheck,
  UserRound,
} from "lucide-react";

interface BrowseResponse {
  path: string;
  parent: string | null;
  directories: { name: string; path: string }[];
}

export default function FolderPicker({
  scanned,
  scanning,
  error,
  onScan,
  onRoleChange,
  onConfirm,
}: {
  scanned: ScanResult | null;
  scanning: boolean;
  error: string | null;
  onScan: (folder: string) => void;
  onRoleChange: (relPath: string, role: string) => void;
  onConfirm: () => void;
}) {
  const [path, setPath] = useState("attune-sample-data/candidates");
  const [browseOpen, setBrowseOpen] = useState(false);
  const [browse, setBrowse] = useState<BrowseResponse | null>(null);
  const [browseLoading, setBrowseLoading] = useState(false);
  const [browseError, setBrowseError] = useState<string | null>(null);

  async function openBrowse(start?: string) {
    setBrowseOpen(true);
    setBrowseError(null);
    setBrowseLoading(true);
    try {
      try {
        setBrowse(await api<BrowseResponse>("/api/browse", { method: "POST", body: JSON.stringify({ path: start ?? path }) }));
      } catch {
        // fallback: start from the project root if the typed path is unreadable
        setBrowse(await api<BrowseResponse>("/api/browse", { method: "POST", body: JSON.stringify({ path: "" }) }));
      }
    } catch (e) {
      setBrowse(null);
      setBrowseError(e instanceof Error ? e.message : "Browse failed");
    } finally {
      setBrowseLoading(false);
    }
  }

  const allTagged = (scanned?.candidates ?? []).every((c) => c.files.every((f) => f.role !== "unclassified"));

  return (
    <div className="space-y-5">
      <Card className="border-emerald-900/10 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <FolderOpen className="h-5 w-5 text-emerald-700" />
            Select the applicant main folder
          </CardTitle>
          <CardDescription>
            One sub-folder per candidate, each holding a CV (PDF) and an optional cover letter. Everything is processed locally - no uploads, no cloud.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="flex-1">
              <Label htmlFor="folder" className="sr-only">
                Main folder path
              </Label>
              <Input
                id="folder"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder="/path/to/applicants"
                className="font-mono text-sm"
                onKeyDown={(e) => e.key === "Enter" && onScan(path)}
              />
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => openBrowse()} className="gap-1.5">
                <Folder className="h-4 w-4" /> Browse
              </Button>
              <Button onClick={() => onScan(path)} disabled={scanning || !path.trim()} className="gap-1.5 bg-emerald-700 hover:bg-emerald-800">
                {scanning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                Scan folder
              </Button>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-700" />
            Local-first: files are read from disk and never leave this machine.
          </div>
          {error && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {scanned && (
        <Card className="border-emerald-900/10 shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg">Validation preview</CardTitle>
            <CardDescription>
              {scanned.candidates.length} candidate{scanned.candidates.length === 1 ? "" : "s"} detected in{" "}
              <span className="font-mono text-xs">{scanned.folder}</span>. Re-tag a file if the automatic classification missed.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {scanned.notes.map((n, i) => (
              <Alert key={i} className="border-amber-500/40 bg-amber-50/60">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                <AlertDescription className="text-amber-900">{typeof n === "string" ? n : `${n.folder}: ${n.note}`}</AlertDescription>
              </Alert>
            ))}
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {scanned.candidates.map((c) => (
                <div key={c.folder} className="rounded-xl border border-slate-200 bg-white p-3">
                  <div className="mb-2 flex items-center gap-2">
                    <UserRound className="h-4 w-4 text-slate-500" />
                    <span className="truncate text-sm font-semibold">{c.folder}</span>
                    {!c.hasCv && (
                      <Badge variant="outline" className="border-rose-300 text-rose-700">
                        no CV
                      </Badge>
                    )}
                    {c.hasCv && !c.hasCover && (
                      <Badge variant="outline" className="border-amber-300 text-amber-700">
                        no cover letter
                      </Badge>
                    )}
                  </div>
                  <Separator className="mb-2" />
                  <div className="space-y-1.5">
                    {c.files.map((f) => (
                      <div key={f.relPath} className="flex items-center gap-2 text-xs">
                        <FileText className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                        <span className="min-w-0 flex-1 truncate font-mono">{f.name}</span>
                        <span className="shrink-0 text-slate-400">{fmtBytes(f.sizeBytes)}</span>
                        <Select
                          value={f.role}
                          onValueChange={(v) => onRoleChange(f.relPath, v)}
                        >
                          <SelectTrigger
                            size="sm"
                            className={`h-7 w-[104px] shrink-0 text-xs ${f.role === "unclassified" ? "border-amber-400 text-amber-700" : ""}`}
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="cv">CV</SelectItem>
                            <SelectItem value="cover">Cover letter</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between pt-2">
              <p className="text-xs text-muted-foreground">
                {allTagged ? "All files classified." : "Some files are unclassified - tag them above."}
              </p>
              <Button onClick={onConfirm} disabled={scanned.candidates.length === 0 || !allTagged} className="gap-1.5 bg-emerald-700 hover:bg-emerald-800">
                Continue to job profile <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog open={browseOpen} onOpenChange={setBrowseOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base">
              <FolderOpen className="h-4 w-4 text-emerald-700" /> Choose the main folder
            </DialogTitle>
          </DialogHeader>
          {browseLoading || !browse ? (
            browseError ? (
              <div className="flex h-40 flex-col items-center justify-center gap-2 text-sm text-rose-700">
                <AlertTriangle className="h-5 w-5" />
                {browseError}
              </div>
            ) : (
              <div className="flex h-40 items-center justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-emerald-700" />
              </div>
            )
          ) : (
            <div className="space-y-3">
              <div className="rounded-lg bg-slate-50 px-3 py-2 font-mono text-xs break-all">{browse.path}</div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!browse.parent}
                  onClick={() => openBrowse(browse.parent ?? undefined)}
                  className="gap-1.5"
                >
                  <FolderUp className="h-3.5 w-3.5" /> Up
                </Button>
                <Button
                  size="sm"
                  onClick={() => {
                    setPath(browse.path);
                    setBrowseOpen(false);
                  }}
                  className="gap-1.5 bg-emerald-700 hover:bg-emerald-800"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" /> Use this folder
                </Button>
              </div>
              <ScrollArea className="h-64 rounded-lg border">
                <div className="p-1">
                  {browse.directories.length === 0 && (
                    <p className="p-3 text-xs text-muted-foreground">No sub-directories.</p>
                  )}
                  {browse.directories.map((d) => (
                    <button
                      key={d.path}
                      className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm hover:bg-emerald-50"
                      onClick={() => openBrowse(d.path)}
                    >
                      <Folder className="h-4 w-4 shrink-0 text-emerald-700" />
                      <span className="truncate">{d.name}</span>
                    </button>
                  ))}
                </div>
              </ScrollArea>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
