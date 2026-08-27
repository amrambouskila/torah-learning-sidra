/** What the Maintenance screen shows before he presses anything. */
export interface MaintenanceStatus {
  readonly catalog_seeded: boolean;
  readonly ledger_seeded: boolean;
  readonly works: number;
  readonly stored_units: number;
  readonly tracks: number;
  readonly advances: number;
  /** When data/ledger.json was last written. Null when it never has been. */
  readonly ledger_exported_at: string | null;
  /** When a correction last wrote its safety copy. Null when none ever has. */
  readonly safety_copy_at: string | null;
}
