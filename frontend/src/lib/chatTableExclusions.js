/** Remove tables from batch match result (exclude from downstream grouping — not a DB delete). */
export function excludeTablesFromMatchResult(matchResult, uidsToRemove) {
  const drop = new Set(uidsToRemove || [])
  if (!matchResult || !drop.size) return matchResult

  const strip = (entries) => (entries || []).filter((mt) => !drop.has(mt.table?._uid))

  const groups = (matchResult.groups || [])
    .map((g) => ({
      ...g,
      matched_tables: strip(g.matched_tables),
    }))
    .filter((g) => g.matched_tables.length > 0)

  const unmatched_tables = (matchResult.unmatched_tables || []).filter(
    (u) => !drop.has(u.table?._uid),
  )

  return { ...matchResult, groups, unmatched_tables }
}
