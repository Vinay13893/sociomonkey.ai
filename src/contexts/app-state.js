// ============================================================================
// APPLICATION STATE - All shared mutable state
// ============================================================================

const root = document.getElementById('app')
// token and user are intentionally left empty here.
// authRestoreSession() in main.js init() restores them from storage after
// verifying the stored token has not expired.
let token = ''
let user = null
let projects = []
let leads = []
let users = []
let activeTab = 'dashboard'
let selectedLeads = new Set()
let selectedLeadId = null
let leadsPage = 1
let leadsPageSize = 25
let activityLogs = []
let availableProducts = []
let currentProduct = localStorage.getItem('current_product') || 'crm'


// Platform admin state (legacy tab within LMS sidebar)
let platformTab = 'tenants'
let mobileNavInitialized = false

// Platform layer routing state
let platformView = 'dashboard'
let platformTenantSlug = null
let platformContext = {}   // e.g. { productCode: 'crm' } when on product hub

// Auth orchestration state
let loginRedirectPath = ''  // path to navigate to after a successful login
