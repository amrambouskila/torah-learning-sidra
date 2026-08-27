/**
 * Where an advance is headed.
 *
 * A ref when Amram said it in words — "5:7", "38b" — which is how he thinks about it. An ordinal
 * only when the rail said it for him and the position is already unambiguous.
 */
export type AdvanceDestination = { readonly toRef: string } | { readonly toOrdinal: number };
