import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './api-client'

// Types mirror backend/app/models/data_upload.py. Keep field names exact.

export type FileType = 'roster' | 'booking' | 'ground_truth'

export interface ValidationIssue {
  stage: string
  severity: 'error' | 'warning'
  reason: string
  column: string | null
  excel_row: number | null
  row_index: number | null
  rule: string | null
  value: string | null
}

export interface ValidationReport {
  file_type: string
  schema_version: number | null
  passed: boolean
  stage_reached: string
  rows_total: number | null
  rows_checked: number | null
  error_count: number
  warning_count: number
  issues: ValidationIssue[]
}

export interface UploadResult {
  status: 'promoted' | 'rejected' | 'duplicate'
  version: number | null
  active_version: number | null
  message: string
  report: ValidationReport
}

export interface DatasetVersion {
  version: number
  sha256: string
  schema_version: number | null
  filename: string
  original_filename: string
  uploaded_by: string
  uploaded_at: string
  rows_total: number | null
  error_count: number
  warning_count: number
  is_active: boolean
}

export interface AuditEntry {
  action: string
  timestamp: string
  user: string
  version: number | null
  detail: string
}

export interface DatasetHistory {
  file_type: string
  active_version: number | null
  versions: DatasetVersion[]
  audit_log: AuditEntry[]
}

export interface SchemaColumn {
  name: string
  dtype: string
  required: boolean
  nullable: boolean
  unique: boolean
  allowed_values: (string | number)[] | null
  min: number | null
  max: number | null
}

export interface SchemaRule {
  name: string
  type: string
  severity: string
  reason: string
}

export interface DatasetSchema {
  file_type: string
  schema_version: number
  display_name: string
  source_file: string | null
  allow_unknown_columns: boolean
  columns: SchemaColumn[]
  business_rules: SchemaRule[]
}

export interface DatasetStatus {
  file_type: FileType
  display_name: string
  /** YAML-declared summary of what this dataset is used for (required vs
   * optional/QA-only) — config-driven, not hardcoded in the component. */
  description: string | null
  schema_version: number
  active_version: number | null
  source: 'uploaded' | 'default'
  uploaded_at: string | null
  uploaded_by: string | null
  rows_total: number | null
}

// --- queries -------------------------------------------------------------- //
export function useDatasetsStatus() {
  return useQuery({
    queryKey: ['data-admin', 'status'],
    queryFn: async () => {
      const res = await apiClient.get<{ datasets: DatasetStatus[] }>('/v1/data/status')
      return res.data.datasets
    },
  })
}

export function useDatasetHistory(fileType: FileType, enabled = true) {
  return useQuery({
    queryKey: ['data-admin', 'history', fileType],
    enabled,
    queryFn: async () => {
      const res = await apiClient.get<DatasetHistory>(`/v1/data/history/${fileType}`)
      return res.data
    },
  })
}

export function useDatasetSchema(fileType: FileType, enabled = true) {
  return useQuery({
    queryKey: ['data-admin', 'schema', fileType],
    enabled,
    queryFn: async () => {
      const res = await apiClient.get<DatasetSchema>(`/v1/data/schema/${fileType}`)
      return res.data
    },
  })
}

// --- mutations ------------------------------------------------------------ //
function toFormData(file: File): FormData {
  const fd = new FormData()
  fd.append('file', file)
  return fd
}

/** Dry run — validate without storing anything. Returns the report. */
export function useValidateUpload() {
  return useMutation({
    mutationFn: async ({ fileType, file }: { fileType: FileType; file: File }) => {
      const res = await apiClient.post<ValidationReport>(
        `/v1/data/validate/${fileType}`,
        toFormData(file),
      )
      return res.data
    },
  })
}

/** Promote a validated file. On a 422 rejection the UploadResult is in
 * `error.response.data.detail` — the caller reads it from the thrown error. */
export function useUploadDataset() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ fileType, file }: { fileType: FileType; file: File }) => {
      const res = await apiClient.post<UploadResult>(
        `/v1/data/upload/${fileType}`,
        toFormData(file),
      )
      return res.data
    },
    onSuccess: (_data, { fileType }) => {
      qc.invalidateQueries({ queryKey: ['data-admin', 'status'] })
      qc.invalidateQueries({ queryKey: ['data-admin', 'history', fileType] })
      invalidateDashboardCachesFor(qc, fileType)
    },
  })
}

export function useRollbackDataset() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (fileType: FileType) => {
      const res = await apiClient.post(`/v1/data/rollback/${fileType}`)
      return res.data
    },
    onSuccess: (_data, fileType) => {
      qc.invalidateQueries({ queryKey: ['data-admin', 'status'] })
      qc.invalidateQueries({ queryKey: ['data-admin', 'history', fileType] })
      invalidateDashboardCachesFor(qc, fileType)
    },
  })
}

/**
 * Every dashboard surface that reads a given dataset must reflect the new
 * active version on the very next request after an upload OR a rollback —
 * no stale reads. `useUploadDataset`/`useRollbackDataset` only ever
 * invalidated their own `data-admin` status/history queries, so every other
 * page (Utilization Home/Search/Results/Overview/Employee/Project pickers,
 * HR/Roster pages, the config-driven filter-option dropdowns) kept serving
 * whatever TanStack Query had cached from before the upload — the backend
 * (`data_loader.reload_*`) was already correct on the very next HTTP
 * request, but the frontend cache never asked for it again until an
 * unrelated refetch or a full page reload happened to occur.
 *
 * `roster` feeds `['roster', ...]` and `['booking', ...]` (Home's donut
 * reads booking summary too); `booking` feeds `['booking', ...]` and every
 * `['utilization', ...]` query (Home/Search/Results/Overview/Employee/
 * Project — all read the booking sheet); `ground_truth` only feeds the
 * admin-only `/qa/reconcile` diagnostic, which isn't cached via
 * TanStack Query today, so no dashboard invalidation is needed for it.
 * Filter-option dropdowns (`['config', 'filters', dataset]`) are also
 * dataset-scoped and invalidated alongside their data.
 */
function invalidateDashboardCachesFor(qc: ReturnType<typeof useQueryClient>, fileType: FileType) {
  if (fileType === 'roster') {
    qc.invalidateQueries({ queryKey: ['roster'] })
    qc.invalidateQueries({ queryKey: ['booking'] })
    qc.invalidateQueries({ queryKey: ['config', 'filters', 'roster'] })
  } else if (fileType === 'booking') {
    qc.invalidateQueries({ queryKey: ['booking'] })
    qc.invalidateQueries({ queryKey: ['utilization'] })
    qc.invalidateQueries({ queryKey: ['config', 'filters', 'booking'] })
  }
  // ground_truth: only consumed by the admin-only /qa/reconcile endpoint,
  // which is not cached via TanStack Query — nothing to invalidate.
}

// --- authenticated file downloads ----------------------------------------- //
async function downloadBlob(url: string, filename: string) {
  const res = await apiClient.get(url, { responseType: 'blob' })
  const blobUrl = URL.createObjectURL(res.data as Blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(blobUrl)
}

export function downloadTemplate(fileType: FileType) {
  return downloadBlob(`/v1/data/template/${fileType}`, `${fileType}_template.xlsx`)
}

export function downloadReport(fileType: FileType, version: number) {
  return downloadBlob(
    `/v1/data/report/${fileType}/${version}`,
    `${fileType}_v${version}_report.xlsx`,
  )
}
