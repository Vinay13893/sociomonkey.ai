const fs = require('fs')
const path = require('path')
const assert = require('assert')

const root = __dirname
const source = fs.readFileSync(path.join(root, 'src/products/lms/lead-sources-v2.js'), 'utf8')

function includes(text, label) {
  assert(source.includes(text), `${label || text} should be present`)
}

function excludes(text, label) {
  assert(!source.includes(text), `${label || text} should be absent`)
}

includes('/api/lead-sources/reports/performance?', 'LMS performance report endpoint')
includes('/api/lead-sources/reports/sync-meta', 'Manual Meta Sync endpoint')
includes('/api/lead-sources/reports/by-source/export.', 'Source performance export')
includes('/api/lead-sources/', 'Lead Sources API usage')
includes('/meta/pull-recent', 'Manual Refresh Forms lead pull path')
includes('full_history: false', 'Refresh Forms must remain bounded')
includes('Submissions', 'Source card must show ingestion submissions')
includes('LMS leads', 'Source card must show accepted LMS lead rows')
includes('s.ingestion_events_count', 'Source card must use canonical submission count')
includes('s.lms_leads_count', 'Source card must use LMS lead-row count')

for (const header of ['Source', 'Form', 'Spend', 'Submissions', 'Source Created', 'Last Sync', 'Unique Leads', 'Processed', 'Duplicate', 'Errors', 'Conversion %', 'CPL']) {
  includes(`<th>${header}</th>`, `Performance Snapshot header ${header}`)
}

includes('_lsv2FetchReport', 'report fetch cache helper')
includes('_lsv2ReportCacheTtlMs = 15000', 'short report cache TTL')
includes('_lsv2ReportCacheClear()', 'report cache invalidation after manual sync')

excludes('Campaign Performance View', 'LMS campaign performance view')
excludes('campaign_page', 'campaign report pagination request')
excludes('campaign_per_page', 'campaign report pagination request')
excludes('campaign_rows ||', 'campaign rows render source')
excludes('/reports/attribution/export', 'campaign attribution export consumption')
excludes('/reports/by-campaign', 'campaign performance API consumption')
excludes('_lsv2ReportsCampaign', 'campaign report pagination functions')
excludes('full_history: true', 'report-triggered full-history Meta pull')

console.log('Phase 5 LMS Lead Sources frontend contract passed')
