// ============================================================================
// PLATFORM CONSTANTS - API base, status colors, pipeline stages
// ============================================================================

const API_BASE = window.API_BASE || 'https://backend-nu-nine-20.vercel.app/api'

const STATUS_COLORS = {
  new:                 { bg: '#dbeafe', color: '#1d4ed8', label: 'New' },
  no_answer:           { bg: '#ffedd5', color: '#ea580c', label: 'No Answer' },
  follow_up:           { bg: '#ede9fe', color: '#7c3aed', label: 'Follow Up' },
  callback_scheduled:  { bg: '#e0e7ff', color: '#4338ca', label: 'Callback Scheduled' },
  interested:          { bg: '#dcfce7', color: '#16a34a', label: 'Interested' },
  site_visit_planned:  { bg: '#cffafe', color: '#0891b2', label: 'Site Visit Planned' },
  site_visit_done:     { bg: '#ccfbf1', color: '#0d9488', label: 'Site Visit Done' },
  negotiation:         { bg: '#fef9c3', color: '#ca8a04', label: 'Negotiation' },
  booking_done:        { bg: '#d1fae5', color: '#059669', label: 'Booking Done' },
  not_interested:      { bg: '#f1f5f9', color: '#64748b', label: 'Not Interested' },
  lost:                { bg: '#fee2e2', color: '#dc2626', label: 'Lost' },
  junk:                { bg: '#e5e7eb', color: '#374151', label: 'Junk' },
  // legacy aliases (backward compat for old activity logs / exports)
  attempted:           { bg: '#ffedd5', color: '#ea580c', label: 'No Answer' },
  connected:           { bg: '#ede9fe', color: '#7c3aed', label: 'Follow Up' },
  assigned:            { bg: '#cffafe', color: '#155e75', label: 'Assigned' },
  unassigned:          { bg: '#fce7f3', color: '#9d174d', label: 'Unassigned' },
}

// Exact display order for the dashboard status grid
const STATUS_ORDER = [
  'new', 'no_answer', 'follow_up', 'callback_scheduled', 'interested',
  'site_visit_planned', 'site_visit_done',
  'negotiation', 'booking_done',
  'not_interested', 'lost', 'junk',
  'assigned', 'unassigned',
]

const PIPELINE_STAGE_LABELS = {
  new: 'New', no_answer: 'No Answer', follow_up: 'Follow Up',
  callback_scheduled: 'Callback Scheduled',
  interested: 'Interested', site_visit_planned: 'Site Visit Planned',
  site_visit_done: 'Site Visit Done', negotiation: 'Negotiation',
  booking_done: 'Booking Done', not_interested: 'Not Interested',
  lost: 'Lost', junk: 'Junk',
}
const PIPELINE_STAGES = Object.keys(PIPELINE_STAGE_LABELS)

// ─── Platform Product Catalogue ───────────────────────────────────────────────

const PRODUCT_CATALOGUE = [
  {
    code: 'lms',         name: 'Lead Management System',
    fullName: 'Lead Management System',
    desc: 'Lead capture, pipeline, team collaboration & performance tracking',
    icon: 'fa-solid fa-building',      color: '#1e3a5f', bg: '#eff6ff', active: true,
  },
  {
    code: 'procurement', name: 'Procurement',
    fullName: 'Procurement & Vendor Management',
    desc: 'Purchase orders, RFQs, vendor approvals & spend analytics',
    icon: 'fa-solid fa-cart-shopping', color: '#f59e0b', bg: '#fff7ed', active: true,
  },
  {
    code: 'wms',         name: '3D Inventory',
    fullName: '3D Inventory Visualization & Management',
    desc: '3D warehouse layout, SKUs, bins & real-time stock tracking',
    icon: 'fa-solid fa-cube',          color: '#3b82f6', bg: '#eff6ff', active: true,
  },
  {
    code: 'amazon',      name: 'Amazon Intelligence',
    fullName: 'Amazon Data Intelligence & Analytics',
    desc: 'Keywords, ranking, ads, competitor analysis & market insights',
    icon: 'fa-brands fa-amazon',       color: '#f97316', bg: '#fff7ed', active: true,
  },
  {
    code: 'crm',         name: 'CRM',
    fullName: 'Customer Relationship Management',
    desc: 'Leads, pipeline, team management & sales analytics',
    icon: 'fa-solid fa-users',         color: '#22c55e', bg: '#f0fdf4', active: false,
  },
  {
    code: 'erp',         name: 'ERP',
    fullName: 'Enterprise Resource Planning',
    desc: 'Finance, operations, HR, supply chain & executive reporting',
    icon: 'fa-solid fa-industry',      color: '#10b981', bg: '#ecfdf5', active: false,
  },
  {
    code: 'realestate',  name: 'Real Estate',
    fullName: 'Real Estate 3D Inventory & Allotment',
    desc: '3D property visualization, unit allotment & booking management',
    icon: 'fa-solid fa-building',      color: '#ef4444', bg: '#fef2f2', active: false,
  },
  {
    code: 'hrms',        name: 'HRMS',
    fullName: 'Human Resource Management System',
    desc: 'Payroll, attendance, leave management, onboarding & appraisals',
    icon: 'fa-solid fa-id-card',       color: '#ec4899', bg: '#fdf2f8', active: false,
  },
]
