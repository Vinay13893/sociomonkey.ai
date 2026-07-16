const fs = require('fs')

const workload = fs.readFileSync('src/products/lms/assign-reassign.js', 'utf8')
const recycle = fs.readFileSync('src/products/lms/recycle-queue.js', 'utf8')

function assert(condition, message) {
  if (!condition) throw new Error(message)
}

assert(workload.includes('_arSelectWorkloadMember'), 'workload member selection missing')
assert(workload.includes('/leads/assign-reassign/workload-preview?'), 'workload preview endpoint missing')
assert(workload.includes('selection_mode'), 'workload move selection mode missing')
assert(workload.includes("random_n"), 'random move mode missing')
assert(workload.includes('AR_LEAD_STATUSES'), 'workload status fallback missing')
assert(workload.includes('_arWorkloadFilterState'), 'workload filter state persistence missing')

assert(recycle.includes('rqView'), 'recycle eligible/excluded view missing')
assert(recycle.includes('rqOwner'), 'recycle owner filter missing')
assert(recycle.includes('rqProject'), 'recycle project filter missing')
assert(recycle.includes('rqSource'), 'recycle source filter missing')
assert(recycle.includes('rqCallbackState'), 'recycle callback filter missing')
assert(recycle.includes('Excluded view is read-only'), 'excluded view read-only guard missing')
assert(recycle.includes("params.set('view', 'eligible')"), 'select-all must stay eligible-only')
assert(recycle.includes('_rqRenderEligibilitySummary'), 'eligibility summary missing')

console.log('Phase 17B allocation frontend contracts passed')
