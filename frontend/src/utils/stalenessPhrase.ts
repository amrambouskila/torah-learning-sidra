/** How long since you last sat with someone, in the unit a person would actually say. */
export function stalenessPhrase(days: number | null): string {
  if (days === null) return "never learned together";
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 14) return `${String(days)} days ago`;
  const weeks = Math.floor(days / 7);
  // Weeks carry up to 62 days, so anything reaching months is at least two of them.
  if (weeks < 9) return `${String(weeks)} weeks ago`;
  return `${String(Math.floor(days / 30))} months ago`;
}
