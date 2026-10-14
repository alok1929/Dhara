import assert from 'node:assert/strict'
import {
  CHAT_STAGE_PILLS,
  chatPillIdForStep,
  chatPillIndexForStep,
  chatPillStatus,
  stepForChatPillId,
} from './chatStages.js'

assert.equal(CHAT_STAGE_PILLS.length, 6)
assert.equal(chatPillIdForStep(1), 'upload')
assert.equal(chatPillIdForStep(2), 'preview')
assert.equal(chatPillIdForStep(3), 'grouping')
assert.equal(chatPillIdForStep(4), 'grouping')
assert.equal(chatPillIdForStep(5), 'classification')
assert.equal(chatPillIdForStep(6), 'harmonisation')
assert.equal(chatPillIdForStep(7), 'publish')

assert.equal(chatPillIndexForStep(4), chatPillIndexForStep(3))
assert.equal(stepForChatPillId('preview'), 2)

assert.equal(chatPillStatus(0, 1, 1), 'current')
assert.equal(chatPillStatus(1, 2, 2), 'current')
assert.equal(chatPillStatus(0, 2, 2), 'completed')

console.log('chatStages.test.mjs: ok')
