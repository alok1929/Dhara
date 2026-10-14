import assert from 'node:assert/strict'
import {
  applyPreviewAiFindFilter,
  createPreviewAiFindFilter,
  isPreviewAiFindActive,
} from './tablePreviewFilter.js'

const rows = [
  { _uid: 'a', title: 'One' },
  { _uid: 'b', title: 'Two' },
]

const filter = createPreviewAiFindFilter({ tableIds: ['b'], rationale: 'second' })
assert.equal(isPreviewAiFindActive(filter), true)
assert.deepEqual(
  applyPreviewAiFindFilter(rows, filter, (t) => t._uid).map((t) => t._uid),
  ['b'],
)
assert.equal(isPreviewAiFindActive(null), false)

console.log('tablePreviewFilter.test.mjs ok')
