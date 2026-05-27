// ============================================================================
// PLATFORM CONSTANTS - API base, status colors, pipeline stages
// ============================================================================

const API_BASE = window.API_BASE || 'http://127.0.0.1:5002/api'

const STATUS_COLORS = {
  new:                 { bg: '#dbeafe', color: '#1d4ed8', label: 'New' },
  attempted:           { bg: '#fef9c3', color: '#854d0e', label: 'Attempted' },
  connected:           { bg: '#d1fae5', color: '#065f46', label: 'Connected' },
  interested:          { bg: '#dcfce7', color: '#166534', label: 'Interested' },
  site_visit_planned:  { bg: '#e0e7ff', color: '#3730a3', label: 'Site Visit Planned' },
  site_visit_done:     { bg: '#ede9fe', color: '#5b21b6', label: 'Site Visit Done' },
  negotiation:         { bg: '#fef3c7', color: '#92400e', label: 'Negotiation' },
  booking_done:        { bg: '#bbf7d0', color: '#14532d', label: 'Booking Done' },
  lost:                { bg: '#fee2e2', color: '#991b1b', label: 'Lost' },
  junk:                { bg: '#f1f5f9', color: '#475569', label: 'Junk' },
  assigned:            { bg: '#cffafe', color: '#155e75', label: 'Assigned' },
  unassigned:          { bg: '#fce7f3', color: '#9d174d', label: 'Unassigned' },
}

// Exact display order for the dashboard status grid
const STATUS_ORDER = [
  'new', 'attempted', 'connected', 'interested',
  'site_visit_planned', 'site_visit_done',
  'negotiation', 'booking_done',
  'lost', 'junk',
  'assigned', 'unassigned',
]

const PIPELINE_STAGE_LABELS = {
  new: 'New', attempted: 'Attempted', connected: 'Connected',
  interested: 'Interested', site_visit_planned: 'Site Visit Planned',
  site_visit_done: 'Site Visit Done', negotiation: 'Negotiation',
  booking_done: 'Booking Done', lost: 'Lost', junk: 'Junk',
}
const PIPELINE_STAGES = Object.keys(PIPELINE_STAGE_LABELS)

// ─── Platform Product Catalogue ───────────────────────────────────────────────

const PRODUCT_CATALOGUE = [
  {
    code: 'crm',         name: 'CRM',
    fullName: 'Customer Relationship Management',
    desc: 'Leads, pipeline, team management & sales analytics',
    icon: 'fa-solid fa-users',         color: '#22c55e', bg: '#f0fdf4', active: true,
  },
  {
    code: 'lms',         name: 'LMS',
    fullName: 'Learning Management System',
    desc: 'Courses, assessments, certifications & learner tracking',
    icon: 'fa-solid fa-graduation-cap', color: '#8b5cf6', bg: '#f5f3ff', active: true,
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
