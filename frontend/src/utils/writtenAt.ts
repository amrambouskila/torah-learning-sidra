/**
 * When a file on disk was last written, in the form he would say it.
 *
 * "Never" rather than a dash: on this screen the difference between a ledger exported last week and
 * one never exported at all is the difference between having a backup and not.
 */
export function writtenAt(iso: string | null): string {
  if (iso === null) return "never";
  const when = new Date(iso);
  return `${when.toLocaleDateString()} ${when.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}
