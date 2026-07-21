import * as React from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Database,
  Download,
  FileSpreadsheet,
  History,
  Info,
  ListChecks,
  RotateCcw,
  Upload,
  XCircle,
} from 'lucide-react'
import axios from 'axios'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import {
  downloadReport,
  downloadTemplate,
  useDatasetHistory,
  useDatasetSchema,
  useDatasetsStatus,
  useRollbackDataset,
  useUploadDataset,
  useValidateUpload,
  type DatasetStatus,
  type FileType,
  type UploadResult,
  type ValidationReport,
} from '@/lib/data-admin-api'

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}

// --------------------------------------------------------------------------- //
// Validation report preview (shared by dry-run + rejection)
// --------------------------------------------------------------------------- //
function ReportSummary({ report }: { report: ValidationReport }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium',
          report.passed
            ? 'bg-emerald-50 text-emerald-700'
            : 'bg-red-50 text-red-700',
        )}
      >
        {report.passed ? (
          <CheckCircle2 className="h-3.5 w-3.5" />
        ) : (
          <XCircle className="h-3.5 w-3.5" />
        )}
        {report.passed ? 'Passed validation' : 'Failed validation'}
      </span>
      <span className="rounded-full bg-muted px-2.5 py-1 text-muted-foreground">
        {report.rows_checked ?? 0} rows checked
      </span>
      {report.error_count > 0 && (
        <span className="rounded-full bg-red-50 px-2.5 py-1 font-medium text-red-700">
          {report.error_count} error{report.error_count === 1 ? '' : 's'}
        </span>
      )}
      {report.warning_count > 0 && (
        <span className="rounded-full bg-amber-50 px-2.5 py-1 font-medium text-amber-700">
          {report.warning_count} warning{report.warning_count === 1 ? '' : 's'}
        </span>
      )}
    </div>
  )
}

function IssuesTable({ report }: { report: ValidationReport }) {
  if (report.issues.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No problems found — this file matches the expected format.
      </p>
    )
  }
  const shown = report.issues.slice(0, 100)
  return (
    <div className="max-h-72 overflow-auto rounded-lg border border-border">
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-muted/80 text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">Severity</th>
            <th className="px-3 py-2 font-medium">Row</th>
            <th className="px-3 py-2 font-medium">Column</th>
            <th className="px-3 py-2 font-medium">Problem</th>
            <th className="px-3 py-2 font-medium">Value</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((issue, i) => (
            <tr key={i} className="border-t border-border/60">
              <td className="px-3 py-2">
                <span
                  className={cn(
                    'inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-medium',
                    issue.severity === 'error'
                      ? 'bg-red-50 text-red-700'
                      : 'bg-amber-50 text-amber-700',
                  )}
                >
                  {issue.severity === 'error' ? (
                    <XCircle className="h-3 w-3" />
                  ) : (
                    <AlertTriangle className="h-3 w-3" />
                  )}
                  {issue.severity}
                </span>
              </td>
              <td className="px-3 py-2 text-muted-foreground">
                {issue.excel_row ?? '—'}
              </td>
              <td className="px-3 py-2 font-mono text-[11px]">
                {issue.column ?? '—'}
              </td>
              <td className="px-3 py-2">{issue.reason}</td>
              <td className="px-3 py-2 font-mono text-[11px] text-muted-foreground">
                {issue.value ?? ''}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {report.issues.length > shown.length && (
        <p className="border-t border-border/60 px-3 py-2 text-[11px] text-muted-foreground">
          Showing first {shown.length} of {report.issues.length} problems.
        </p>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Upload panel (per dataset): pick -> validate (dry run) -> confirm
// --------------------------------------------------------------------------- //
function UploadPanel({ dataset }: { dataset: DatasetStatus }) {
  const fileType = dataset.file_type
  const [file, setFile] = React.useState<File | null>(null)
  const [report, setReport] = React.useState<ValidationReport | null>(null)
  const [outcome, setOutcome] = React.useState<UploadResult | null>(null)
  const inputRef = React.useRef<HTMLInputElement>(null)

  const validate = useValidateUpload()
  const upload = useUploadDataset()

  const reset = () => {
    setFile(null)
    setReport(null)
    setOutcome(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const onPick = async (f: File | null) => {
    setReport(null)
    setOutcome(null)
    setFile(f)
    if (!f) return
    try {
      const r = await validate.mutateAsync({ fileType, file: f })
      setReport(r)
    } catch (err) {
      // Security-stage rejections come back as 422 with a report body.
      if (axios.isAxiosError(err) && err.response?.data) {
        const data = err.response.data
        if (data.issues) setReport(data as ValidationReport)
        else if (data.detail?.report) setReport(data.detail.report)
      }
    }
  }

  const onConfirm = async () => {
    if (!file) return
    try {
      const result = await upload.mutateAsync({ fileType, file })
      setOutcome(result)
      setReport(result.report)
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data?.detail) {
        const detail = err.response.data.detail as UploadResult
        setOutcome(detail)
        setReport(detail.report)
      }
    }
  }

  const busy = validate.isPending || upload.isPending

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx"
          className="hidden"
          onChange={(e) => onPick(e.target.files?.[0] ?? null)}
        />
        <Button
          size="sm"
          variant="outline"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
        >
          <FileSpreadsheet className="h-4 w-4" />
          {file ? 'Choose a different file' : 'Choose .xlsx file'}
        </Button>
        {file && (
          <span className="truncate text-xs text-muted-foreground" title={file.name}>
            {file.name}
          </span>
        )}
      </div>

      {validate.isPending && (
        <p className="text-xs text-muted-foreground">Validating…</p>
      )}

      {report && !outcome && (
        <div className="space-y-3 rounded-xl border border-border bg-muted/30 p-3">
          <ReportSummary report={report} />
          <IssuesTable report={report} />
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              onClick={onConfirm}
              disabled={!report.passed || busy}
              title={
                report.passed
                  ? 'Make this file the live data'
                  : 'Fix the errors above before uploading'
              }
            >
              <Upload className="h-4 w-4" />
              {upload.isPending ? 'Uploading…' : 'Confirm & make live'}
            </Button>
            <Button size="sm" variant="ghost" onClick={reset} disabled={busy}>
              Cancel
            </Button>
            {!report.passed && (
              <span className="text-xs text-muted-foreground">
                This file was rejected — the live data is unchanged.
              </span>
            )}
          </div>
        </div>
      )}

      {outcome && (
        <div
          className={cn(
            'flex items-start gap-2 rounded-xl border p-3 text-sm',
            outcome.status === 'rejected'
              ? 'border-red-200 bg-red-50 text-red-800'
              : 'border-emerald-200 bg-emerald-50 text-emerald-800',
          )}
        >
          {outcome.status === 'rejected' ? (
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
          ) : (
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
          )}
          <div className="space-y-2">
            <p>{outcome.message}</p>
            <Button size="sm" variant="ghost" onClick={reset}>
              Upload another
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Schema dialog
// --------------------------------------------------------------------------- //
function SchemaDialog({
  fileType,
  open,
  onOpenChange,
}: {
  fileType: FileType
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  const { data, isLoading } = useDatasetSchema(fileType, open)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl p-0">
        <div className="border-b border-border p-5">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <ListChecks className="h-5 w-5 text-primary" />
            Expected format — {data?.display_name ?? fileType}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            The exact columns and rules an upload is checked against
            {data ? ` (schema v${data.schema_version})` : ''}.
          </p>
        </div>
        <div className="max-h-[60vh] overflow-auto p-5">
          {isLoading || !data ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <div className="space-y-5">
              <div className="overflow-auto rounded-lg border border-border">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/80 text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2 font-medium">Column</th>
                      <th className="px-3 py-2 font-medium">Type</th>
                      <th className="px-3 py-2 font-medium">Required</th>
                      <th className="px-3 py-2 font-medium">Allowed values</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.columns.map((c) => (
                      <tr key={c.name} className="border-t border-border/60">
                        <td className="px-3 py-2 font-mono text-[11px]">{c.name}</td>
                        <td className="px-3 py-2 text-muted-foreground">{c.dtype}</td>
                        <td className="px-3 py-2">
                          {c.required ? (
                            <span className="text-red-600">required</span>
                          ) : (
                            <span className="text-muted-foreground">optional</span>
                          )}
                          {c.unique ? ' · unique' : ''}
                        </td>
                        <td className="px-3 py-2 text-muted-foreground">
                          {c.allowed_values
                            ? c.allowed_values.join(', ')
                            : c.min != null || c.max != null
                              ? `${c.min ?? '−∞'} … ${c.max ?? '∞'}`
                              : 'any'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {data.business_rules.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold">Cross-field rules</h3>
                  <ul className="space-y-1.5 text-xs text-muted-foreground">
                    {data.business_rules.map((r) => (
                      <li key={r.name} className="flex items-start gap-2">
                        <span
                          className={cn(
                            'mt-0.5 rounded px-1.5 py-0.5 font-medium',
                            r.severity === 'error'
                              ? 'bg-red-50 text-red-700'
                              : 'bg-amber-50 text-amber-700',
                          )}
                        >
                          {r.severity}
                        </span>
                        <span>{r.reason}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <Button
                size="sm"
                variant="outline"
                onClick={() => downloadTemplate(fileType)}
              >
                <Download className="h-4 w-4" />
                Download blank template
              </Button>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

// --------------------------------------------------------------------------- //
// History dialog (versions + rollback + audit)
// --------------------------------------------------------------------------- //
function HistoryDialog({
  fileType,
  open,
  onOpenChange,
}: {
  fileType: FileType
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  const { data, isLoading } = useDatasetHistory(fileType, open)
  const rollback = useRollbackDataset()
  const canRollback =
    !!data?.active_version &&
    data.versions.some((v) => v.version < (data.active_version ?? 0))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl p-0">
        <div className="flex items-center justify-between border-b border-border p-5">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <History className="h-5 w-5 text-primary" />
              Version history
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Every upload is kept. Roll back to make the previous version live again.
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => rollback.mutate(fileType)}
            disabled={!canRollback || rollback.isPending}
            title={
              canRollback
                ? 'Restore the previous version'
                : 'No earlier version to roll back to'
            }
          >
            <RotateCcw className="h-4 w-4" />
            {rollback.isPending ? 'Rolling back…' : 'Roll back'}
          </Button>
        </div>
        <div className="max-h-[60vh] space-y-4 overflow-auto p-5">
          {isLoading || !data ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : data.versions.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No uploads yet — the dashboard is showing the bundled default file.
            </p>
          ) : (
            <div className="overflow-auto rounded-lg border border-border">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/80 text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 font-medium">Version</th>
                    <th className="px-3 py-2 font-medium">Uploaded</th>
                    <th className="px-3 py-2 font-medium">By</th>
                    <th className="px-3 py-2 font-medium">Rows</th>
                    <th className="px-3 py-2 font-medium">Warnings</th>
                    <th className="px-3 py-2 font-medium">Report</th>
                  </tr>
                </thead>
                <tbody>
                  {[...data.versions].reverse().map((v) => (
                    <tr key={v.version} className="border-t border-border/60">
                      <td className="px-3 py-2 font-medium">
                        v{v.version}
                        {v.is_active && (
                          <span className="ml-2 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                            active
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {fmtDate(v.uploaded_at)}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">{v.uploaded_by}</td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {v.rows_total ?? '—'}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {v.warning_count}
                      </td>
                      <td className="px-3 py-2">
                        <button
                          className="inline-flex items-center gap-1 text-primary hover:underline"
                          onClick={() => downloadReport(fileType, v.version)}
                        >
                          <Download className="h-3 w-3" />
                          xlsx
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data && data.audit_log.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-semibold">Activity log</h3>
              <ul className="space-y-1 text-xs text-muted-foreground">
                {[...data.audit_log].reverse().map((a, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <Clock className="h-3 w-3 shrink-0" />
                    <span className="text-foreground/70">{fmtDate(a.timestamp)}</span>
                    <span>· {a.detail} ({a.user})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

// --------------------------------------------------------------------------- //
// Dataset card
// --------------------------------------------------------------------------- //
function DatasetCard({ dataset }: { dataset: DatasetStatus }) {
  const [schemaOpen, setSchemaOpen] = React.useState(false)
  const [historyOpen, setHistoryOpen] = React.useState(false)

  return (
    <Card className="hover:translate-y-0 hover:shadow-card">
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Database className="h-5 w-5" />
          </span>
          <div>
            <CardTitle className="text-base">{dataset.display_name}</CardTitle>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {dataset.source === 'uploaded' ? (
                <>
                  Live: uploaded v{dataset.active_version} ·{' '}
                  {dataset.rows_total ?? '—'} rows
                </>
              ) : (
                <>Live: bundled default file</>
              )}
            </p>
          </div>
        </div>
        <span
          className={cn(
            'rounded-full px-2.5 py-1 text-[11px] font-medium',
            dataset.source === 'uploaded'
              ? 'bg-emerald-50 text-emerald-700'
              : 'bg-muted text-muted-foreground',
          )}
        >
          {dataset.source === 'uploaded' ? `v${dataset.active_version}` : 'default'}
        </span>
      </CardHeader>
      <CardContent className="space-y-4">
        {dataset.source === 'uploaded' && (
          <p className="text-xs text-muted-foreground">
            Uploaded {fmtDate(dataset.uploaded_at)} by {dataset.uploaded_by}
          </p>
        )}

        <UploadPanel dataset={dataset} />

        <div className="flex flex-wrap gap-2 border-t border-border/60 pt-3">
          <Button size="sm" variant="ghost" onClick={() => setSchemaOpen(true)}>
            <ListChecks className="h-4 w-4" />
            Expected format
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => downloadTemplate(dataset.file_type)}
          >
            <Download className="h-4 w-4" />
            Template
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setHistoryOpen(true)}>
            <History className="h-4 w-4" />
            History
          </Button>
        </div>
      </CardContent>

      <SchemaDialog
        fileType={dataset.file_type}
        open={schemaOpen}
        onOpenChange={setSchemaOpen}
      />
      <HistoryDialog
        fileType={dataset.file_type}
        open={historyOpen}
        onOpenChange={setHistoryOpen}
      />
    </Card>
  )
}

// --------------------------------------------------------------------------- //
// Page
// --------------------------------------------------------------------------- //
export function DataManagementPage() {
  const { data: datasets, isLoading, isError } = useDatasetsStatus()

  return (
    <div className="space-y-5">
      <Card className="hover:translate-y-0 hover:shadow-card">
        <CardContent className="flex items-start gap-3 p-5">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Info className="h-5 w-5" />
          </span>
          <div className="space-y-1 text-sm">
            <p className="font-medium">Upload new data to update the dashboard</p>
            <p className="text-muted-foreground">
              Pick an Excel file for a dataset below. It is checked against the
              expected format first — you'll see any problems before it goes live,
              and a rejected file never changes the dashboard. Every upload is
              versioned, so you can roll back at any time.
            </p>
          </div>
        </CardContent>
      </Card>

      {isLoading && (
        <p className="text-sm text-muted-foreground">Loading datasets…</p>
      )}
      {isError && (
        <p className="text-sm text-red-600">
          Could not load datasets. You may not have permission to view this page.
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {datasets?.map((d) => (
          <DatasetCard key={d.file_type} dataset={d} />
        ))}
      </div>
    </div>
  )
}
