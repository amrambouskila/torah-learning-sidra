/** The catalog against the expected counts. */
export interface VerifyResult {
  readonly matches: boolean;
  /** One sentence per mismatch, exactly as the CLI prints them. Empty when the catalog is good. */
  readonly failures: readonly string[];
}
