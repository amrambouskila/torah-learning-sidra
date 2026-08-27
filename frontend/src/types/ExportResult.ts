/** What one ledger export — or one restore — moved. */
export interface ExportResult {
  readonly path: string;
  readonly tracks: number;
  readonly advances: number;
  readonly chavrusas: number;
  readonly tags: number;
  readonly calendar_days: number;
}
