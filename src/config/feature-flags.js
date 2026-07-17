// ============================================================================
// FEATURE FLAGS — Definitions of all available per-tenant feature toggles.
//
// Each flag has:
//   key         — used in FeatureFlag.flag_key and isTenantFeatureEnabled()
//   label       — shown in the Platform Admin feature editor
//   description — tooltip/helper text
//   default     — fallback value when no tenant-specific flag is set
//   product     — which product this flag belongs to (for grouping)
// ============================================================================

var FEATURE_FLAGS = [
  // ── LMS Core ───────────────────────────────────────────────────────────────
  {
    key: 'pipeline',
    label: 'Sales Pipeline',
    description: 'Kanban board for tracking leads through sales stages.',
    default: true,
    product: 'lms',
  },
  {
    key: 'reports',
    label: 'Analytics & Reports',
    description: 'Charts and performance analytics for sales teams.',
    default: true,
    product: 'lms',
  },
  {
    key: 'bulk_import',
    label: 'Bulk Lead Import',
    description: 'Import leads in bulk from Excel / CSV files.',
    default: true,
    product: 'lms',
  },
  {
    key: 'export',
    label: 'Data Export',
    description: 'Export leads and reports to Excel / CSV.',
    default: true,
    product: 'lms',
  },
  {
    key: 'team_management',
    label: 'Team Management',
    description: 'Add and manage team members, roles, and assignments.',
    default: true,
    product: 'lms',
  },
  {
    key: 'activity_logs',
    label: 'Activity Logs',
    description: 'Detailed audit trail of all user actions.',
    default: true,
    product: 'lms',
  },

  // ── LMS Advanced (may require higher plan) ─────────────────────────────────
  {
    key: 'automation',
    label: 'Automation Rules',
    description: 'Set up automated workflows and triggers. (Coming soon)',
    default: false,
    product: 'lms',
  },
  {
    key: 'ai_assist',
    label: 'AI Assistant',
    description: 'AI-powered lead scoring and recommendations. (Coming soon)',
    default: false,
    product: 'lms',
  },

  // ── Platform-wide ──────────────────────────────────────────────────────────
  {
    key: 'multi_product',
    label: 'Multi-Product Switcher',
    description: 'Allow users to switch between enabled products in the sidebar.',
    default: true,
    product: 'platform',
  },
]
