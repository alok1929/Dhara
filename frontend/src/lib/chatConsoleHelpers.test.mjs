import assert from 'node:assert/strict'
import { excludeTablesFromMatchResult } from './chatTableExclusions.js'

const sample = {
  groups: [{
    matched_tables: [
      { table: { _uid: 'a', title: 'A' } },
      { table: { _uid: 'b', title: 'B' } },
    ],
  }],
  unmatched_tables: [{ table: { _uid: 'c', title: 'C' } }],
}

const next = excludeTablesFromMatchResult(sample, ['b'])
assert.equal(next.groups[0].matched_tables.length, 1)
assert.equal(next.groups[0].matched_tables[0].table._uid, 'a')
assert.equal(next.unmatched_tables.length, 1)

console.log('chatConsoleHelpers.test.mjs: ok')
