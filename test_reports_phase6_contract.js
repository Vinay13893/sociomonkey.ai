const fs = require('fs')
const path = require('path')
const assert = require('assert')

const root = __dirname
const leadSources = fs.readFileSync(path.join(root, 'src/products/lms/lead-sources-v2.js'), 'utf8')

function includes(text, label) {
  assert(leadSources.includes(text), `${label || text} should be present`)
}

function excludes(text, label) {
  assert(!leadSources.includes(text), `${label || text} should be absent`)
}

includes('Source Performance', 'source-level performance table')
includes('Forms', 'forms table remains visible')
includes('var sourceRowsData = reportData.source_rows || []', 'source rows drive spend table')
includes('var formRowsData = reportData.form_rows || []', 'form rows remain separate')
includes('<th>Source</th><th>Spend</th><th>Unique Leads</th><th>Processed</th><th>Duplicate</th><th>Errors</th><th>Conversion %</th><th>CPL</th>', 'source spend headers')
includes('<th>Source</th><th>Form</th><th>Total Leads</th><th>Unique Leads</th><th>Processed</th><th>Duplicate</th><th>Errors</th><th>Conversion %</th>', 'form headers without spend')

excludes('reportData.form_rows || reportData.source_rows', 'forms must not drive spend table')
excludes('<th>Source</th><th>Form</th><th>Spend</th>', 'form table must not include spend')
excludes('<th>Form</th><th>Spend</th>', 'form spend column must be absent')

console.log('Phase 6 reports frontend contract passed')
