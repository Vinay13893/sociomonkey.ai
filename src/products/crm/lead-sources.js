/**
 * Lead Sources – Admin UI  (Phase META-1.1)
 * ==========================================
 * Tabs:
 *   Sources     – list all sources, test/enable/disable
 *   Connect     – guided OAuth wizard (Meta and Google)
 *   Add/Edit    – manual credential form for webhooks/generic
 *   Test Lead   – inject synthetic lead through full pipeline
 *   Validate    – run 7-item PASS/FAIL validation report
 *   Logs        – paginated ingestion log
 *   Reports     – by-source and by-campaign tables
 *
 * Depends on: authFetch() from auth.js, showToast() from ui-utils.js
 */

// ─── Constants ────────────────────────────────────────────────────────────────

const SOURCE_TYPE_LABELS = {
    meta:            '🟦 Facebook / Instagram',
    google:          '🔴 Google Lead Form',
    webhook:         '🌐 Website / Webhook',
    housing:         '🏠 Housing.com',
    magicbricks:     '🧱 MagicBricks',
    ninetynineacres: '🏡 99acres',
    indiamart:       '🏭 IndiaMART',
    whatsapp_form:   '💬 WhatsApp Form',
};

const DUP_MODE_LABELS = {
    skip:             'Skip (ignore duplicate)',
    update:           'Update existing lead',
    create_duplicate: 'Create anyway',
    flag:             'Create and flag as duplicate',
};

const ASSIGN_STRATEGY_LABELS = {
    none:          'None (leave unassigned)',
    round_robin:   'Round Robin',
    fixed_user:    'Fixed User',
    project_based: 'Project Sales Manager',
    manager_based: 'Fixed Manager',
};

// ─── Module state ─────────────────────────────────────────────────────────────

let _lsTab     = 'sources';
let _lsEditId  = null;
let _lsSources = [];
let _lsLogPage = 1;
let _lsLogTotal = 0;
const _lsLogPerPage = 25;

// OAuth wizard state
let _metaWizard   = {};
let _googleWizard = {};

// ─── Entry Point ──────────────────────────────────────────────────────────────

function renderLeadSources() {
    const el = document.getElementById('content');
    if (!el) return;

    el.innerHTML = `
    <div class="page-header d-flex align-items-center justify-content-between mb-3">
        <div>
            <h2 class="mb-0">🔗 Lead Sources</h2>
            <p class="text-muted mb-0 small">Manage lead ingestion — Facebook, Google, website forms and more.</p>
        </div>
    </div>

    <ul class="nav nav-tabs mb-4" id="ls-tabs">
        <li class="nav-item"><a class="nav-link active" href="#" data-tab="sources">Sources</a></li>
        <li class="nav-item"><a class="nav-link" href="#" data-tab="connect">+ Connect</a></li>
        <li class="nav-item"><a class="nav-link" href="#" data-tab="add">Manual / Webhook</a></li>
        <li class="nav-item"><a class="nav-link" href="#" data-tab="testlead">Test Lead</a></li>
        <li class="nav-item"><a class="nav-link" href="#" data-tab="validate">✅ Validate</a></li>
        <li class="nav-item"><a class="nav-link" href="#" data-tab="logs">Logs</a></li>
        <li class="nav-item"><a class="nav-link" href="#" data-tab="reports">Reports</a></li>
    </ul>
    <div id="ls-body"></div>`;

    document.querySelectorAll('#ls-tabs .nav-link').forEach(function(a) {
        a.addEventListener('click', function(e) {
            e.preventDefault();
            document.querySelectorAll('#ls-tabs .nav-link').forEach(function(x) { x.classList.remove('active'); });
            a.classList.add('active');
            _lsTab = a.dataset.tab;
            _lsRenderTab(_lsTab);
        });
    });

    _lsRenderTab('sources');
}

function _lsSwitchTab(tab) {
    _lsTab = tab;
    document.querySelectorAll('#ls-tabs .nav-link').forEach(function(a) {
        a.classList.toggle('active', a.dataset.tab === tab);
    });
    _lsRenderTab(tab);
}

function _lsRenderTab(tab) {
    const el = document.getElementById('ls-body');
    if (!el) return;
    if (tab === 'sources')  return _lsLoadSources();
    if (tab === 'connect')  return _lsRenderConnect();
    if (tab === 'add')      return _lsRenderForm(null);
    if (tab === 'testlead') return _lsRenderTestLead();
    if (tab === 'validate') return _lsRenderValidate();
    if (tab === 'logs')     return _lsLoadLogs(1);
    if (tab === 'reports')  return _lsLoadReports();
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB: Sources list
// ══════════════════════════════════════════════════════════════════════════════

async function _lsLoadSources() {
    const el = document.getElementById('ls-body');
    el.innerHTML = '<div class="text-center py-5 text-muted">Loading...</div>';
    const res = await authFetch('/api/lead-sources');
    if (!res.ok) { el.innerHTML = '<p class="text-danger">Failed to load sources.</p>'; return; }
    const data = await res.json();
    _lsSources = data.sources || [];
    _lsRenderSources();
}

function _lsRenderSources() {
    const el = document.getElementById('ls-body');
    if (!_lsSources.length) {
        el.innerHTML = `
        <div class="text-center py-5">
            <p class="text-muted mb-3">No lead sources configured yet.</p>
            <button class="btn btn-primary me-2" onclick="_lsSwitchTab('connect')">🔗 Connect Meta or Google</button>
            <button class="btn btn-outline-secondary" onclick="_lsSwitchTab('add')">+ Manual / Webhook</button>
        </div>`;
        return;
    }

    var rows = _lsSources.map(function(s) {
        var statusBadge = s.is_active
            ? '<span class="badge bg-success">Active</span>'
            : '<span class="badge bg-secondary">Disabled</span>';
        var connBadge = s.permission_status === 'ok'
            ? '<span class="badge bg-info ms-1">Connected</span>'
            : s.permission_status === 'partial' ? '<span class="badge bg-warning text-dark ms-1">Partial</span>'
            : s.permission_status === 'error'   ? '<span class="badge bg-danger ms-1">Error</span>'
            : '';
        var errCell = s.total_errors ? '<span class="text-danger">' + s.total_errors + '</span>' : '0';
        return '<tr>' +
            '<td><strong>' + _esc(s.name) + '</strong><br><small class="text-muted">' + (SOURCE_TYPE_LABELS[s.source_type] || s.source_type) + '</small></td>' +
            '<td>' + statusBadge + connBadge + '</td>' +
            '<td>' + (s.connected_account ? '<span class="text-truncate d-block" style="max-width:160px" title="' + _esc(s.connected_account) + '">' + _esc(s.connected_account) + '</span>' : '<span class="text-muted">&mdash;</span>') + '</td>' +
            '<td>' + (s.total_leads_ingested || 0) + '</td>' +
            '<td>' + errCell + '</td>' +
            '<td>' + (s.last_lead_at ? _lsRelTime(s.last_lead_at) : '&mdash;') + '</td>' +
            '<td class="text-end text-nowrap">' +
                '<button class="btn btn-sm btn-outline-secondary me-1" onclick="_lsOpenEdit(' + s.id + ')">Edit</button>' +
                '<button class="btn btn-sm btn-outline-info me-1" onclick="_lsOpenTestLead(' + s.id + ')">&#9654; Test</button>' +
                '<button class="btn btn-sm btn-outline-primary me-1" onclick="_lsTestSource(' + s.id + ', event)">Ping</button>' +
                '<button class="btn btn-sm ' + (s.is_active ? 'btn-outline-warning' : 'btn-outline-success') + '" onclick="_lsToggleSource(' + s.id + ', ' + (!s.is_active) + ')">' +
                (s.is_active ? 'Disable' : 'Enable') + '</button>' +
            '</td>' +
        '</tr>';
    }).join('');

    el.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-3">
        <span class="text-muted small">${_lsSources.length} source(s) configured</span>
        <div>
            <button class="btn btn-primary btn-sm me-2" onclick="_lsSwitchTab('connect')">🔗 Connect New</button>
            <button class="btn btn-outline-secondary btn-sm" onclick="_lsSwitchTab('add')">+ Manual</button>
        </div>
    </div>
    <table class="table table-hover align-middle">
        <thead class="table-light">
            <tr><th>Source</th><th>Status</th><th>Connected Account</th>
                <th>Leads</th><th>Errors</th><th>Last Lead</th><th></th></tr>
        </thead>
        <tbody>${rows}</tbody>
    </table>`;
}

async function _lsTestSource(id, evt) {
    var btn = evt ? evt.target : document.querySelector('[onclick="_lsTestSource(' + id + ')"]');
    if (btn) { btn.disabled = true; btn.textContent = '...'; }
    var res = await authFetch('/api/lead-sources/' + id + '/test', { method: 'POST' });
    if (btn) { btn.disabled = false; btn.textContent = 'Ping'; }
    var data = await res.json();
    var t = data.test || {};
    var icon = t.result === 'pass' ? '✅' : t.result === 'partial' ? '⚠️' : '❌';
    showToast(icon + ' ' + (t.message || 'Test completed'), t.result === 'pass' ? 'success' : 'warning');
    await _lsLoadSources();
}

async function _lsToggleSource(id, enable) {
    var res = await authFetch('/api/lead-sources/' + id + '/' + (enable ? 'enable' : 'disable'), { method: 'POST' });
    if (!res.ok) { showToast('Failed to update source', 'danger'); return; }
    showToast(enable ? 'Source enabled' : 'Source disabled', 'success');
    await _lsLoadSources();
}

function _lsOpenEdit(id) {
    _lsEditId = id;
    var source = _lsSources.find(function(s) { return s.id === id; });
    _lsSwitchTab('add');
    if (source) _lsRenderForm(source);
}

function _lsOpenTestLead(id) {
    _lsSwitchTab('testlead');
    setTimeout(function() {
        var sel = document.getElementById('ls-test-source-id');
        if (sel) sel.value = id;
    }, 120);
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB: Connect — guided OAuth wizard chooser
// ══════════════════════════════════════════════════════════════════════════════

function _lsRenderConnect() {
    var el = document.getElementById('ls-body');
    el.innerHTML = `
    <div class="row g-4">
        <div class="col-md-5">
            <div class="card h-100">
                <div class="card-body">
                    <h5 class="card-title">🟦 Connect Meta (Facebook / Instagram)</h5>
                    <p class="card-text text-muted small">Guided OAuth wizard. Select your page and lead forms.</p>
                    <ul class="text-muted small mb-3">
                        <li>Enter App credentials</li>
                        <li>Exchange access token</li>
                        <li>Select Page</li>
                        <li>Select Lead Forms</li>
                        <li>Save &amp; Activate</li>
                    </ul>
                    <button class="btn btn-primary w-100" onclick="_lsStartMetaWizard()">Connect Meta →</button>
                </div>
            </div>
        </div>
        <div class="col-md-5">
            <div class="card h-100">
                <div class="card-body">
                    <h5 class="card-title">🔴 Connect Google Lead Form</h5>
                    <p class="card-text text-muted small">OAuth 2.0 connection. Receive leads from Google Ads Lead Form extensions.</p>
                    <ul class="text-muted small mb-3">
                        <li>Enter OAuth credentials</li>
                        <li>Authorize Google Account</li>
                        <li>Configure Customer ID</li>
                        <li>Save &amp; Activate</li>
                    </ul>
                    <button class="btn btn-danger w-100" onclick="_lsStartGoogleWizard()">Connect Google →</button>
                </div>
            </div>
        </div>
        <div class="col-md-2">
            <div class="card h-100 bg-light">
                <div class="card-body text-center">
                    <p class="text-muted small mt-2">Need a custom webhook?</p>
                    <button class="btn btn-outline-secondary btn-sm w-100" onclick="_lsSwitchTab('add')">+ Webhook / Custom</button>
                </div>
            </div>
        </div>
    </div>
    <div id="ls-wizard-area" class="mt-4"></div>`;
}

// ─── META WIZARD ──────────────────────────────────────────────────────────────

function _lsStartMetaWizard() {
    _metaWizard = { step: 1, appId: '', appSecret: '', longToken: '', user: null, pages: [], selectedPage: null, forms: [], selectedForms: [], verifyToken: '' };
    _lsRenderMetaWizard();
}

function _lsRenderMetaWizard() {
    var el = document.getElementById('ls-wizard-area');
    if (!el) return;
    var w = _metaWizard;

    var stepLabels = ['App Credentials', 'Get Token', 'Select Page', 'Select Forms', 'Save'];
    var stepNav = stepLabels.map(function(s, i) {
        var cls = (i + 1 === w.step) ? 'bg-primary' : (i + 1 < w.step) ? 'bg-success' : 'bg-secondary';
        return '<span class="badge ' + cls + ' me-1">' + (i + 1 < w.step ? '✓' : (i + 1)) + '. ' + s + '</span>';
    }).join('');

    var body = '';

    if (w.step === 1) {
        body = `
        <p class="text-muted small">Enter your Meta App credentials from
            <a href="https://developers.facebook.com/apps" target="_blank">Meta for Developers → Your App → Settings → Basic</a>.
        </p>
        <div class="mb-3">
            <label class="form-label">App ID</label>
            <input class="form-control" id="mw-app-id" placeholder="123456789012345" value="${_esc(w.appId)}">
        </div>
        <div class="mb-3">
            <label class="form-label">App Secret</label>
            <input type="password" class="form-control" id="mw-app-secret" value="${_esc(w.appSecret)}">
        </div>
        <div class="mb-3">
            <label class="form-label">Webhook Verify Token <small class="text-muted">(any secret string you choose)</small></label>
            <input class="form-control" id="mw-verify-token" placeholder="my_secret_token_2024" value="${_esc(w.verifyToken)}">
        </div>
        <button class="btn btn-primary" onclick="_lsMetaStep1Next()">Next →</button>`;

    } else if (w.step === 2) {
        body = `
        <p class="text-muted small">Go to <a href="https://developers.facebook.com/tools/explorer" target="_blank">Meta Graph Explorer</a>, request permissions
            <code>pages_manage_ads</code>, <code>pages_read_engagement</code>, <code>leads_retrieval</code>, then paste your short-lived User Access Token below.
        </p>
        <div class="mb-3">
            <label class="form-label">Short-Lived User Access Token</label>
            <input type="password" class="form-control" id="mw-short-token" placeholder="EAABsbCS...">
        </div>
        <div class="d-flex gap-2">
            <button class="btn btn-outline-secondary" onclick="_metaWizard.step=1; _lsRenderMetaWizard()">← Back</button>
            <button class="btn btn-primary" onclick="_lsMetaStep2Exchange(event)">Exchange Token →</button>
        </div>`;

    } else if (w.step === 3) {
        var pageItems = w.pages.length ? w.pages.map(function(p) {
            var active = (w.selectedPage && w.selectedPage.id === p.id) ? 'active' : '';
            return '<div class="list-group-item list-group-item-action d-flex justify-content-between align-items-center ' + active + '" style="cursor:pointer" onclick="_lsMetaSelectPage(\'' + _esc(p.id) + '\')">' +
                '<div><strong>' + _esc(p.name) + '</strong><br><small class="opacity-75">ID: ' + _esc(p.id) + '</small></div>' +
                (active ? '<span>✓</span>' : '') +
            '</div>';
        }).join('') : '<p class="text-muted p-3">No pages found.</p>';

        body = '<p class="text-muted small">Logged in as <strong>' + _esc(w.user ? w.user.name : '') + '</strong>. Select a Facebook Page.</p>' +
            '<div class="list-group mb-3">' + pageItems + '</div>' +
            '<div class="d-flex gap-2">' +
                '<button class="btn btn-outline-secondary" onclick="_metaWizard.step=2; _lsRenderMetaWizard()">← Back</button>' +
                '<button class="btn btn-primary" onclick="_lsMetaStep3Next(event)" ' + (!w.selectedPage ? 'disabled' : '') + '>Next →</button>' +
            '</div>';

    } else if (w.step === 4) {
        var formItems = w.forms.length ? w.forms.map(function(f) {
            var checked = w.selectedForms.find(function(x) { return x.id === f.id; }) ? 'checked' : '';
            var statusColor = f.status === 'ACTIVE' ? 'success' : 'secondary';
            return '<div class="list-group-item">' +
                '<div class="form-check">' +
                    '<input class="form-check-input" type="checkbox" id="mwf-' + f.id + '" ' + checked + ' onchange="_lsMetaToggleForm(\'' + _esc(f.id) + '\', \'' + _esc(f.name) + '\', this.checked)">' +
                    '<label class="form-check-label w-100" for="mwf-' + f.id + '">' +
                        '<strong>' + _esc(f.name) + '</strong>' +
                        '<span class="badge bg-' + statusColor + ' ms-2">' + _esc(f.status || 'UNKNOWN') + '</span>' +
                        (f.leads_count ? '<small class="text-muted ms-2">' + f.leads_count + ' leads</small>' : '') +
                    '</label>' +
                '</div>' +
            '</div>';
        }).join('') : '<p class="text-muted p-3">No lead forms found. Make sure you have active Lead Ads on this page.</p>';

        body = '<p class="text-muted small">Select lead forms to receive. Selected: <strong>' + w.selectedForms.length + '</strong></p>' +
            '<div class="list-group mb-3">' + formItems + '</div>' +
            '<div class="mb-3">' +
                '<button class="btn btn-sm btn-outline-secondary me-2" onclick="_lsMetaSelectAllForms()">Select All</button>' +
                '<button class="btn btn-sm btn-outline-secondary" onclick="_lsMetaClearForms()">Clear</button>' +
            '</div>' +
            '<div class="d-flex gap-2">' +
                '<button class="btn btn-outline-secondary" onclick="_metaWizard.step=3; _lsRenderMetaWizard()">← Back</button>' +
                '<button class="btn btn-primary" onclick="_metaWizard.step=5; _lsRenderMetaWizard()">Next →</button>' +
            '</div>';

    } else if (w.step === 5) {
        body = `
        <div class="row g-3">
            <div class="col-md-6">
                <h6>Connection Summary</h6>
                <table class="table table-sm">
                    <tr><th>Account</th><td>${_esc(w.user ? w.user.name : '')}</td></tr>
                    <tr><th>Page</th><td>${_esc(w.selectedPage ? w.selectedPage.name : '')}</td></tr>
                    <tr><th>Forms Selected</th><td>${w.selectedForms.length}</td></tr>
                </table>
            </div>
            <div class="col-md-6">
                <label class="form-label">Source Name</label>
                <input class="form-control mb-3" id="mw-source-name" value="${_esc('Meta - ' + (w.selectedPage ? w.selectedPage.name : ''))}">
                <div class="alert alert-info small mb-0">
                    <strong>After saving:</strong> In Meta App → Webhooks, set:<br>
                    <span>Verify Token: <code>${_esc(w.verifyToken)}</code></span><br>
                    <span>Subscribe: <code>leadgen</code></span>
                </div>
            </div>
        </div>
        <div class="d-flex gap-2 mt-3">
            <button class="btn btn-outline-secondary" onclick="_metaWizard.step=4; _lsRenderMetaWizard()">← Back</button>
            <button class="btn btn-success" onclick="_lsMetaSave(event)">✅ Save &amp; Activate</button>
        </div>`;
    }

    el.innerHTML = '<div class="card"><div class="card-header d-flex align-items-center gap-2"><strong>🟦 Connect Meta</strong><div class="ms-auto">' + stepNav + '</div></div><div class="card-body">' + body + '</div></div>';
}

function _lsMetaStep1Next() {
    var appId       = (document.getElementById('mw-app-id').value || '').trim();
    var appSecret   = (document.getElementById('mw-app-secret').value || '').trim();
    var verifyToken = (document.getElementById('mw-verify-token').value || '').trim();
    if (!appId || !appSecret) { showToast('App ID and App Secret are required', 'danger'); return; }
    _metaWizard.appId       = appId;
    _metaWizard.appSecret   = appSecret;
    _metaWizard.verifyToken = verifyToken || ('lms_verify_' + Date.now());
    _metaWizard.step = 2;
    _lsRenderMetaWizard();
}

async function _lsMetaStep2Exchange(evt) {
    var shortToken = (document.getElementById('mw-short-token').value || '').trim();
    if (!shortToken) { showToast('Please paste your short-lived token', 'danger'); return; }
    var btn = evt ? evt.target : null;
    if (btn) { btn.disabled = true; btn.textContent = 'Exchanging...'; }
    var res = await authFetch('/api/lead-sources/meta/exchange-token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ short_lived_token: shortToken, app_id: _metaWizard.appId, app_secret: _metaWizard.appSecret }),
    });
    if (btn) { btn.disabled = false; btn.textContent = 'Exchange Token →'; }
    var data = await res.json();
    if (!res.ok) { showToast(data.error || 'Token exchange failed', 'danger'); return; }
    _metaWizard.longToken = data.long_lived_token;
    _metaWizard.user      = data.user;
    _metaWizard.pages     = data.pages || [];
    _metaWizard.step      = 3;
    _lsRenderMetaWizard();
}

function _lsMetaSelectPage(pageId) {
    _metaWizard.selectedPage = _metaWizard.pages.find(function(p) { return p.id === pageId; }) || null;
    _lsRenderMetaWizard();
}

async function _lsMetaStep3Next(evt) {
    if (!_metaWizard.selectedPage) { showToast('Select a page first', 'danger'); return; }
    var btn = evt ? evt.target : null;
    if (btn) { btn.disabled = true; btn.textContent = 'Loading forms...'; }
    var res = await authFetch('/api/lead-sources/meta/page-forms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ page_id: _metaWizard.selectedPage.id, page_access_token: _metaWizard.selectedPage.access_token }),
    });
    if (btn) { btn.disabled = false; btn.textContent = 'Next →'; }
    var data = await res.json();
    if (!res.ok) { showToast(data.error || 'Could not load forms', 'danger'); return; }
    _metaWizard.forms = data.forms || [];
    _metaWizard.selectedForms = _metaWizard.forms.slice(); // select all by default
    _metaWizard.step = 4;
    _lsRenderMetaWizard();
}

function _lsMetaToggleForm(id, name, checked) {
    if (checked) {
        if (!_metaWizard.selectedForms.find(function(f) { return f.id === id; }))
            _metaWizard.selectedForms.push({ id: id, name: name });
    } else {
        _metaWizard.selectedForms = _metaWizard.selectedForms.filter(function(f) { return f.id !== id; });
    }
}

function _lsMetaSelectAllForms() { _metaWizard.selectedForms = _metaWizard.forms.slice(); _lsRenderMetaWizard(); }
function _lsMetaClearForms()     { _metaWizard.selectedForms = []; _lsRenderMetaWizard(); }

async function _lsMetaSave(evt) {
    var name = ((document.getElementById('mw-source-name') || {}).value || '').trim()
               || ('Meta - ' + (_metaWizard.selectedPage ? _metaWizard.selectedPage.name : ''));
    var btn = evt ? evt.target : null;
    if (btn) { btn.disabled = true; btn.textContent = 'Saving...'; }
    var res = await authFetch('/api/lead-sources/meta/save-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            name:              name,
            app_id:            _metaWizard.appId,
            app_secret:        _metaWizard.appSecret,
            user_token:        _metaWizard.longToken,
            page_id:           _metaWizard.selectedPage.id,
            page_name:         _metaWizard.selectedPage.name,
            page_access_token: _metaWizard.selectedPage.access_token,
            selected_forms:    _metaWizard.selectedForms,
            verify_token:      _metaWizard.verifyToken,
        }),
    });
    if (btn) { btn.disabled = false; btn.textContent = 'Save & Activate'; }
    var data = await res.json();
    if (!res.ok) { showToast(data.error || 'Save failed', 'danger'); return; }
    showToast('✅ Meta source connected!', 'success');
    await _lsLoadSources();
    _lsSwitchTab('sources');
}

// ─── GOOGLE WIZARD ────────────────────────────────────────────────────────────

function _lsStartGoogleWizard() {
    var _googleRedirectUri = 'https://smk-backend-api.vercel.app/api/lead-sources/google/oauth/callback';
    _googleWizard = { step: 1, clientId: '', clientSecret: '', redirectUri: _googleRedirectUri, authCode: '', accessToken: '', refreshToken: '', user: null };
    _lsRenderGoogleWizard();
}

function _lsRenderGoogleWizard() {
    var el = document.getElementById('ls-wizard-area');
    if (!el) return;
    var w = _googleWizard;

    var stepLabels = ['App Credentials', 'Authorize', 'Details', 'Save'];
    var stepNav = stepLabels.map(function(s, i) {
        var cls = (i + 1 === w.step) ? 'bg-danger' : (i + 1 < w.step) ? 'bg-success' : 'bg-secondary';
        return '<span class="badge ' + cls + ' me-1">' + (i + 1 < w.step ? '✓' : (i + 1)) + '. ' + s + '</span>';
    }).join('');

    var body = '';

    if (w.step === 1) {
        var defaultRedirect = 'https://smk-backend-api.vercel.app/api/lead-sources/google/oauth/callback';
        body = `
        <p class="text-muted small">Create OAuth 2.0 credentials at
            <a href="https://console.cloud.google.com/apis/credentials" target="_blank">Google Cloud Console</a>.
            Add <code>${_esc(defaultRedirect)}</code> as an authorised redirect URI.
        </p>
        <div class="mb-3">
            <label class="form-label">Client ID</label>
            <input class="form-control" id="gw-client-id" placeholder="1234...apps.googleusercontent.com" value="${_esc(w.clientId)}">
        </div>
        <div class="mb-3">
            <label class="form-label">Client Secret</label>
            <input type="password" class="form-control" id="gw-client-secret" placeholder="GOCSPX-..." value="${_esc(w.clientSecret)}">
        </div>
        <div class="mb-3">
            <label class="form-label">Redirect URI</label>
            <input class="form-control" id="gw-redirect-uri" value="${_esc(w.redirectUri || defaultRedirect)}">
        </div>
        <button class="btn btn-danger" onclick="_lsGoogleStep1Next()">Next →</button>`;

    } else if (w.step === 2) {
        var scopes = 'https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/adwords';
        var oauthUrl = 'https://accounts.google.com/o/oauth2/v2/auth?client_id=' + encodeURIComponent(w.clientId) +
            '&redirect_uri=' + encodeURIComponent(w.redirectUri) +
            '&response_type=code&scope=' + encodeURIComponent(scopes) +
            '&access_type=offline&prompt=consent';
        body = `
        <p class="text-muted small">Click the button to open Google authorization. After approving, copy the <code>?code=</code> value from the redirect URL.</p>
        <a class="btn btn-danger mb-3" href="${_esc(oauthUrl)}" target="_blank">🔗 Open Google Authorization</a>
        <div class="mb-3">
            <label class="form-label">Authorization Code</label>
            <input class="form-control font-monospace" id="gw-auth-code" placeholder="4/0AX4XfWj...">
        </div>
        <div class="d-flex gap-2">
            <button class="btn btn-outline-secondary" onclick="_googleWizard.step=1; _lsRenderGoogleWizard()">← Back</button>
            <button class="btn btn-danger" onclick="_lsGoogleStep2Exchange(event)">Exchange Code →</button>
        </div>`;

    } else if (w.step === 3) {
        body = `
        <p class="text-muted small">Connected as <strong>${_esc(w.user ? w.user.email : '')}</strong>.</p>
        <div class="mb-3">
            <label class="form-label">Google Ads Customer ID <small class="text-muted">(optional, e.g. 123-456-7890)</small></label>
            <input class="form-control" id="gw-customer-id" placeholder="123-456-7890">
        </div>
        <div class="mb-3">
            <label class="form-label">Campaign / Form label <small class="text-muted">(your reference label)</small></label>
            <input class="form-control" id="gw-campaign-label" placeholder="Mumbai Apartments Q2 2026">
        </div>
        <div class="d-flex gap-2">
            <button class="btn btn-outline-secondary" onclick="_googleWizard.step=2; _lsRenderGoogleWizard()">← Back</button>
            <button class="btn btn-danger" onclick="_googleWizard.step=4; _lsRenderGoogleWizard()">Next →</button>
        </div>`;

    } else if (w.step === 4) {
        body = `
        <div class="row g-3">
            <div class="col-md-6">
                <h6>Connection Summary</h6>
                <table class="table table-sm">
                    <tr><th>Account</th><td>${_esc(w.user ? w.user.email : '')}</td></tr>
                </table>
            </div>
            <div class="col-md-6">
                <label class="form-label">Source Name</label>
                <input class="form-control mb-3" id="gw-source-name" value="${_esc('Google - ' + (w.user ? w.user.email : ''))}">
                <div class="alert alert-info small mb-0">
                    After saving, go to Google Ads → Lead Form Extensions → Webhook and enter the webhook URL shown in the Sources list.
                </div>
            </div>
        </div>
        <div class="d-flex gap-2 mt-3">
            <button class="btn btn-outline-secondary" onclick="_googleWizard.step=3; _lsRenderGoogleWizard()">← Back</button>
            <button class="btn btn-success" onclick="_lsGoogleSave(event)">✅ Save &amp; Activate</button>
        </div>`;
    }

    el.innerHTML = '<div class="card"><div class="card-header d-flex align-items-center gap-2"><strong>🔴 Connect Google</strong><div class="ms-auto">' + stepNav + '</div></div><div class="card-body">' + body + '</div></div>';
}

function _lsGoogleStep1Next() {
    var clientId     = (document.getElementById('gw-client-id').value || '').trim();
    var clientSecret = (document.getElementById('gw-client-secret').value || '').trim();
    var redirectUri  = (document.getElementById('gw-redirect-uri').value || '').trim();
    if (!clientId || !clientSecret) { showToast('Client ID and Client Secret are required', 'danger'); return; }
    _googleWizard.clientId     = clientId;
    _googleWizard.clientSecret = clientSecret;
    _googleWizard.redirectUri  = redirectUri;
    _googleWizard.step = 2;
    _lsRenderGoogleWizard();
}

async function _lsGoogleStep2Exchange(evt) {
    var code = (document.getElementById('gw-auth-code').value || '').trim();
    if (!code) { showToast('Paste the authorization code', 'danger'); return; }
    var btn = evt ? evt.target : null;
    if (btn) { btn.disabled = true; btn.textContent = 'Exchanging...'; }
    var res = await authFetch('/api/lead-sources/google/exchange-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: code, client_id: _googleWizard.clientId, client_secret: _googleWizard.clientSecret, redirect_uri: _googleWizard.redirectUri }),
    });
    if (btn) { btn.disabled = false; btn.textContent = 'Exchange Code →'; }
    var data = await res.json();
    if (!res.ok) { showToast(data.error || 'Code exchange failed', 'danger'); return; }
    _googleWizard.accessToken  = data.access_token;
    _googleWizard.refreshToken = data.refresh_token;
    _googleWizard.user         = data.user;
    _googleWizard.step = 3;
    _lsRenderGoogleWizard();
}

async function _lsGoogleSave(evt) {
    var name       = ((document.getElementById('gw-source-name') || {}).value || '').trim();
    var customerId = ((document.getElementById('gw-customer-id') || {}).value || '').trim();
    var label      = ((document.getElementById('gw-campaign-label') || {}).value || '').trim();
    var btn = evt ? evt.target : null;
    if (btn) { btn.disabled = true; btn.textContent = 'Saving...'; }
    var res = await authFetch('/api/lead-sources/google/save-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            name:           name || ('Google - ' + (_googleWizard.user ? _googleWizard.user.email : '')),
            client_id:      _googleWizard.clientId,
            client_secret:  _googleWizard.clientSecret,
            refresh_token:  _googleWizard.refreshToken,
            customer_id:    customerId,
            user_email:     _googleWizard.user ? _googleWizard.user.email : '',
            selected_forms: label ? [{ id: 'custom', name: label }] : [],
        }),
    });
    if (btn) { btn.disabled = false; btn.textContent = 'Save & Activate'; }
    var data = await res.json();
    if (!res.ok) { showToast(data.error || 'Save failed', 'danger'); return; }
    showToast('✅ Google source connected!', 'success');
    await _lsLoadSources();
    _lsSwitchTab('sources');
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB: Manual / Webhook — Add / Edit form
// ══════════════════════════════════════════════════════════════════════════════

function _lsRenderForm(source) {
    _lsEditId = source ? source.id : null;
    var el = document.getElementById('ls-body');
    var isEdit = !!source;
    var creds = (source && source.credentials) || {};

    var sourceTypeOpts = Object.keys(SOURCE_TYPE_LABELS).map(function(v) {
        return '<option value="' + v + '"' + (source && source.source_type === v ? ' selected' : '') + '>' + _esc(SOURCE_TYPE_LABELS[v]) + '</option>';
    }).join('');

    var dupModeOpts = Object.keys(DUP_MODE_LABELS).map(function(v) {
        var sel = (source ? source.dup_mode : 'skip') === v ? ' selected' : '';
        return '<option value="' + v + '"' + sel + '>' + _esc(DUP_MODE_LABELS[v]) + '</option>';
    }).join('');

    var assignOpts = Object.keys(ASSIGN_STRATEGY_LABELS).map(function(v) {
        var sel = (source ? source.assign_strategy : 'none') === v ? ' selected' : '';
        return '<option value="' + v + '"' + sel + '>' + _esc(ASSIGN_STRATEGY_LABELS[v]) + '</option>';
    }).join('');

    el.innerHTML = `
    <h5>${isEdit ? 'Edit Source' : 'Add Source (Manual / Webhook)'}</h5>
    <form id="ls-form" class="mt-3" style="max-width:680px">
        <div class="mb-3">
            <label class="form-label">Name <span class="text-danger">*</span></label>
            <input type="text" class="form-control" id="ls-name" value="${_esc(source ? source.name : '')}" required>
        </div>
        <div class="mb-3">
            <label class="form-label">Platform <span class="text-danger">*</span></label>
            <select class="form-select" id="ls-source-type" onchange="_lsOnSourceTypeChange()" ${isEdit ? 'disabled' : ''}>
                ${sourceTypeOpts}
            </select>
            ${isEdit ? '<input type="hidden" id="ls-source-type-hidden" value="' + _esc(source.source_type) + '">' : ''}
        </div>
        <div id="ls-creds-area"></div>
        <hr>
        <h6>Field Mapping <small class="text-muted fw-normal">(JSON: source field → LMS field)</small></h6>
        <textarea class="form-control font-monospace" id="ls-field-mapping" rows="3" placeholder='{"phone_number": "phone"}'>${source && source.field_mapping ? JSON.stringify(source.field_mapping, null, 2) : ''}</textarea>
        <hr>
        <h6>Default Values <small class="text-muted fw-normal">(JSON: applied to every lead)</small></h6>
        <textarea class="form-control font-monospace" id="ls-default-values" rows="3" placeholder='{"project_id": 5}'>${source && source.default_values ? JSON.stringify(source.default_values, null, 2) : ''}</textarea>
        <hr>
        <h6>Duplicate Detection</h6>
        <div class="form-check form-switch mb-2">
            <input class="form-check-input" type="checkbox" id="ls-dup-phone" ${!source || source.dup_check_phone ? 'checked' : ''}>
            <label class="form-check-label" for="ls-dup-phone">Check duplicate by phone</label>
        </div>
        <div class="form-check form-switch mb-3">
            <input class="form-check-input" type="checkbox" id="ls-dup-email" ${source && source.dup_check_email ? 'checked' : ''}>
            <label class="form-check-label" for="ls-dup-email">Check duplicate by email</label>
        </div>
        <div class="mb-3">
            <label class="form-label">When duplicate found</label>
            <select class="form-select" id="ls-dup-mode">${dupModeOpts}</select>
        </div>
        <hr>
        <h6>Auto-Assignment</h6>
        <div class="mb-3">
            <select class="form-select" id="ls-assign-strategy" onchange="_lsOnAssignStrategyChange()">${assignOpts}</select>
        </div>
        <div id="ls-assign-user-area"></div>
        <div class="mt-4 d-flex gap-2">
            <button type="submit" class="btn btn-primary">${isEdit ? 'Save Changes' : 'Create Source'}</button>
            <button type="button" class="btn btn-outline-secondary" onclick="_lsSwitchTab('sources')">Cancel</button>
            ${isEdit ? '<button type="button" class="btn btn-outline-danger ms-auto" onclick="_lsDeleteSource(' + source.id + ')">Delete</button>' : ''}
        </div>
    </form>`;

    _lsOnSourceTypeChange(source);
    _lsOnAssignStrategyChange(source);
    document.getElementById('ls-form').addEventListener('submit', async function(e) { e.preventDefault(); await _lsSaveSource(); });
}

function _lsOnSourceTypeChange(source) {
    var typeEl = document.getElementById('ls-source-type') || document.getElementById('ls-source-type-hidden');
    var type = typeEl ? typeEl.value : '';
    var el = document.getElementById('ls-creds-area');
    if (!el) return;
    var creds = (source && source.credentials) || {};
    var webhookBlock = source
        ? '<div class="alert alert-info py-2 small mb-3"><strong>Webhook URL:</strong> <code id="ls-webhook-url">' + location.origin + '/api/ingestion/' + source.source_type + '/' + source.webhook_token + '</code><button class="btn btn-sm btn-outline-secondary ms-2" onclick="navigator.clipboard.writeText(document.getElementById(\'ls-webhook-url\').textContent); showToast(\'Copied!\',\'success\')">Copy</button></div>'
        : '';
    if (type === 'meta') {
        el.innerHTML = webhookBlock +
            '<div class="mb-2"><label class="form-label">Page Access Token</label><input type="password" class="form-control" id="ls-cred-access_token" value="' + _esc(creds.access_token || '') + '"></div>' +
            '<div class="mb-2"><label class="form-label">App Secret</label><input type="password" class="form-control" id="ls-cred-app_secret" value="' + _esc(creds.app_secret || '') + '"></div>' +
            '<div class="mb-3"><label class="form-label">Webhook Verify Token</label><input class="form-control" id="ls-cred-verify_token" value="' + _esc(creds.verify_token || '') + '"></div>';
    } else if (type === 'google') {
        el.innerHTML = webhookBlock +
            '<div class="mb-2"><label class="form-label">Client ID</label><input class="form-control" id="ls-cred-client_id" value="' + _esc(creds.client_id || '') + '"></div>' +
            '<div class="mb-2"><label class="form-label">Client Secret</label><input type="password" class="form-control" id="ls-cred-client_secret" value="' + _esc(creds.client_secret || '') + '"></div>' +
            '<div class="mb-2"><label class="form-label">Refresh Token</label><input type="password" class="form-control" id="ls-cred-refresh_token" value="' + _esc(creds.refresh_token || '') + '"></div>' +
            '<div class="mb-3"><label class="form-label">Customer ID</label><input class="form-control" id="ls-cred-customer_id" value="' + _esc(creds.customer_id || '') + '"></div>';
    } else {
        el.innerHTML = webhookBlock +
            '<div class="mb-3"><label class="form-label">Webhook Secret (optional, for HMAC)</label><input type="password" class="form-control" id="ls-cred-webhook_secret" value="' + _esc(creds.webhook_secret || '') + '"></div>';
    }
}

function _lsOnAssignStrategyChange(source) {
    var stratEl = document.getElementById('ls-assign-strategy');
    var strat = stratEl ? stratEl.value : (source ? source.assign_strategy : 'none');
    var el = document.getElementById('ls-assign-user-area');
    if (!el) return;
    if (strat === 'none') { el.innerHTML = ''; return; }
    if (strat === 'fixed_user' || strat === 'manager_based') {
        var label = strat === 'fixed_user' ? 'Assign to User (User ID)' : 'Manager User ID';
        var val = source ? (strat === 'fixed_user' ? source.assign_fixed_user_id : source.assign_manager_id) : '';
        el.innerHTML = '<div class="mb-3"><label class="form-label">' + label + '</label><input type="number" class="form-control" id="ls-assign-user-id" value="' + (val || '') + '"></div>';
    } else if (strat === 'round_robin') {
        var pool = source && source.rr_user_pool ? source.rr_user_pool.join(', ') : '';
        el.innerHTML = '<div class="mb-3"><label class="form-label">User ID Pool (comma-separated, blank = all team members)</label><input class="form-control" id="ls-rr-pool" value="' + _esc(pool) + '" placeholder="3, 7, 12"></div>';
    } else { el.innerHTML = ''; }
}

async function _lsSaveSource() {
    var typeEl = document.getElementById('ls-source-type') || document.getElementById('ls-source-type-hidden');
    var sourceType = typeEl ? typeEl.value : '';
    var creds = {};
    ['access_token','app_secret','verify_token','client_id','client_secret','refresh_token','customer_id','webhook_secret'].forEach(function(k) {
        var cel = document.getElementById('ls-cred-' + k);
        if (cel && cel.value.trim()) creds[k] = cel.value.trim();
    });
    var fieldMapping = {};
    try { fieldMapping = JSON.parse(document.getElementById('ls-field-mapping').value || '{}'); }
    catch (e) { showToast('Field mapping is not valid JSON', 'danger'); return; }
    var defaultValues = {};
    try { defaultValues = JSON.parse(document.getElementById('ls-default-values').value || '{}'); }
    catch (e) { showToast('Default values is not valid JSON', 'danger'); return; }

    var strat = document.getElementById('ls-assign-strategy').value;
    var body = {
        name:            (document.getElementById('ls-name').value || '').trim(),
        source_type:     sourceType,
        credentials:     creds,
        field_mapping:   fieldMapping,
        default_values:  defaultValues,
        dup_check_phone: document.getElementById('ls-dup-phone').checked,
        dup_check_email: document.getElementById('ls-dup-email').checked,
        dup_mode:        document.getElementById('ls-dup-mode').value,
        assign_strategy: strat,
    };
    if (strat === 'fixed_user')   body.assign_fixed_user_id = parseInt((document.getElementById('ls-assign-user-id') || {}).value) || null;
    else if (strat === 'manager_based') body.assign_manager_id = parseInt((document.getElementById('ls-assign-user-id') || {}).value) || null;
    else if (strat === 'round_robin') {
        var raw = ((document.getElementById('ls-rr-pool') || {}).value || '').trim();
        body.rr_user_pool = raw ? raw.split(',').map(function(x) { return parseInt(x.trim()); }).filter(Boolean) : [];
    }

    var url    = _lsEditId ? '/api/lead-sources/' + _lsEditId : '/api/lead-sources';
    var method = _lsEditId ? 'PUT' : 'POST';
    var res = await authFetch(url, { method: method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    var data = await res.json();
    if (!res.ok) { showToast(data.error || 'Save failed', 'danger'); return; }
    showToast(_lsEditId ? 'Source updated' : 'Source created', 'success');
    _lsEditId = null;
    await _lsLoadSources();
    _lsSwitchTab('sources');
}

async function _lsDeleteSource(id) {
    if (!confirm('Disable this source? Existing leads are not affected.')) return;
    var res = await authFetch('/api/lead-sources/' + id, { method: 'DELETE' });
    if (!res.ok) { showToast('Failed', 'danger'); return; }
    showToast('Source disabled', 'success');
    _lsEditId = null;
    await _lsLoadSources();
    _lsSwitchTab('sources');
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB: Test Lead
// ══════════════════════════════════════════════════════════════════════════════

function _lsRenderTestLead() {
    var el = document.getElementById('ls-body');
    if (!_lsSources.length) {
        el.innerHTML = '<div class="alert alert-warning">No sources configured. <a href="#" onclick="_lsSwitchTab(\'connect\')">Connect one first.</a></div>';
        return;
    }
    var sourceOpts = _lsSources.map(function(s) {
        return '<option value="' + s.id + '">' + _esc(s.name) + ' (' + s.source_type + ')</option>';
    }).join('');
    el.innerHTML = `
    <div class="row g-4">
        <div class="col-md-5">
            <h5>Inject Test Lead</h5>
            <p class="text-muted small">Fire a synthetic lead through the full ingestion pipeline and verify each stage.</p>
            <div class="mb-3">
                <label class="form-label">Source <span class="text-danger">*</span></label>
                <select class="form-select" id="ls-test-source-id">${sourceOpts}</select>
            </div>
            <div class="mb-2">
                <label class="form-label">Name <small class="text-muted">(optional)</small></label>
                <input class="form-control" id="ls-test-name" placeholder="Auto-generated if blank">
            </div>
            <div class="mb-2">
                <label class="form-label">Phone <small class="text-muted">(optional)</small></label>
                <input class="form-control" id="ls-test-phone" placeholder="Auto-generated if blank">
            </div>
            <div class="mb-2">
                <label class="form-label">Email <small class="text-muted">(optional)</small></label>
                <input class="form-control" id="ls-test-email" placeholder="Auto-generated if blank">
            </div>
            <div class="mb-3">
                <label class="form-label">Campaign Name</label>
                <input class="form-control" id="ls-test-campaign" placeholder="Test Campaign">
            </div>
            <button class="btn btn-primary w-100" onclick="_lsRunTestLead(event)">▶ Run Test Lead</button>
        </div>
        <div class="col-md-7" id="ls-test-result">
            <div class="text-muted small pt-5 text-center">Results will appear here after you run a test lead.</div>
        </div>
    </div>`;
}

async function _lsRunTestLead(evt) {
    var sourceId = (document.getElementById('ls-test-source-id') || {}).value;
    if (!sourceId) { showToast('Select a source', 'danger'); return; }
    var btn = evt ? evt.target : null;
    if (btn) { btn.disabled = true; btn.textContent = 'Running...'; }

    var body = {};
    var nameVal = ((document.getElementById('ls-test-name') || {}).value || '').trim();
    var phoneVal = ((document.getElementById('ls-test-phone') || {}).value || '').trim();
    var emailVal = ((document.getElementById('ls-test-email') || {}).value || '').trim();
    var campVal = ((document.getElementById('ls-test-campaign') || {}).value || '').trim();
    if (nameVal)  body.name = nameVal;
    if (phoneVal) body.phone = phoneVal;
    if (emailVal) body.email = emailVal;
    if (campVal)  body.campaign_name = campVal;

    var res = await authFetch('/api/lead-sources/' + sourceId + '/inject-test-lead', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (btn) { btn.disabled = false; btn.textContent = '▶ Run Test Lead'; }

    var data = await res.json();
    var el = document.getElementById('ls-test-result');

    if (!res.ok) {
        el.innerHTML = '<div class="alert alert-danger">' + _esc(data.error || 'Request failed') + '</div>';
        return;
    }

    var r = data.result || {};
    var checks = data.checks || {};
    var ev = data.evidence || {};
    var lead = ev.lead || {};
    var activity = ev.activity || {};
    var log = ev.log || {};

    var statusColor = r.status === 'created' ? 'success' : r.status === 'error' ? 'danger' : 'warning';
    var statusIcon  = r.status === 'created' ? '✅' : r.status === 'error' ? '❌' : '⚠️';

    // also update inject-test-lead checklist to show push+action board
    function checkRow(label, passed) {
        return '<tr><td>' + _esc(label) + '</td><td><span class="badge bg-' + (passed ? 'success' : 'danger') + '">' + (passed ? 'PASS' : 'FAIL') + '</span></td></tr>';
    }

    el.innerHTML =
        '<div class="alert alert-' + statusColor + ' d-flex align-items-center mb-3">' +
            '<span class="fs-4 me-3">' + statusIcon + '</span>' +
            '<div><strong>Pipeline Status: ' + _esc(r.status || '?') + '</strong><br><small>' + _esc(r.message || '') + '</small></div>' +
        '</div>' +
        '<h6>LMS Pipeline Checklist</h6>' +
        '<table class="table table-sm table-bordered"><tbody>' +
            checkRow('Lead Created', checks.lead_created) +
            checkRow('Pipeline Ran Successfully', checks.pipeline_ran) +
            checkRow('Activity Logged', checks.activity_logged) +
            checkRow('Assignment Rule Applied', checks.assignment_applied) +
            checkRow('Push Notification Created', checks.push_notification_created) +
            checkRow('Action Board Updated', checks.action_board_updated) +
        '</tbody></table>' +
        (lead.id ? '<h6>Lead Created</h6><table class="table table-sm">' +
            '<tr><th>ID</th><td>#' + lead.id + '</td></tr>' +
            '<tr><th>Name</th><td>' + _esc(lead.name || '') + '</td></tr>' +
            '<tr><th>Phone</th><td>' + _esc(lead.phone || '') + '</td></tr>' +
            '<tr><th>Email</th><td>' + _esc(lead.email || '') + '</td></tr>' +
            '<tr><th>Assigned To</th><td>' + (lead.assigned_to_name ? _esc(lead.assigned_to_name) : '<span class="text-muted">Unassigned</span>') + '</td></tr>' +
            '<tr><th>Status</th><td>' + _esc(lead.status || '') + '</td></tr>' +
        '</table>' : '') +
        (activity.id ? '<h6>Activity Timeline</h6><div class="alert alert-light small">' + _esc(activity.description || '') + '</div>' : '') +
        (log.id ? '<h6>Ingestion Log</h6><table class="table table-sm">' +
            '<tr><th>Log ID</th><td>' + log.id + '</td></tr>' +
            '<tr><th>Status</th><td>' + _esc(log.status || '') + '</td></tr>' +
            '<tr><th>Campaign</th><td>' + _esc(log.campaign_name || '—') + '</td></tr>' +
        '</table>' : '');
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB: Validate — PASS/FAIL report
// ══════════════════════════════════════════════════════════════════════════════

function _lsRenderValidate() {
    var el = document.getElementById('ls-body');
    var metaSources   = _lsSources.filter(function(s) { return s.source_type === 'meta'; });
    var googleSources = _lsSources.filter(function(s) { return s.source_type === 'google'; });

    var metaOpts = [{ id: '', name: '— None —' }].concat(metaSources).map(function(s) {
        return '<option value="' + _esc(String(s.id)) + '">' + _esc(s.name || '— None —') + '</option>';
    }).join('');
    var googleOpts = [{ id: '', name: '— None —' }].concat(googleSources).map(function(s) {
        return '<option value="' + _esc(String(s.id)) + '">' + _esc(s.name || '— None —') + '</option>';
    }).join('');

    el.innerHTML = `
    <div class="row g-4">
        <div class="col-md-4">
            <h5>🧪 Phase META-1.1 Validation</h5>
            <p class="text-muted small">Runs all 7 checks and generates a PASS/FAIL deployment report.</p>
            <div class="mb-3">
                <label class="form-label">Meta Source</label>
                <select class="form-select" id="ls-val-meta">${metaOpts}</select>
            </div>
            <div class="mb-3">
                <label class="form-label">Google Source</label>
                <select class="form-select" id="ls-val-google">${googleOpts}</select>
            </div>
            <button class="btn btn-dark w-100" onclick="_lsRunValidation(event)">▶ Run Validation</button>
            <p class="text-muted small mt-2">⚠ Test leads will be created in your database.</p>
        </div>
        <div class="col-md-8" id="ls-val-result">
            <div class="text-muted small pt-4 text-center">Select sources and click Run Validation.</div>
        </div>
    </div>`;
}

async function _lsRunValidation(evt) {
    var metaId   = (document.getElementById('ls-val-meta') || {}).value;
    var googleId = (document.getElementById('ls-val-google') || {}).value;
    var btn = evt ? evt.target : null;
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Running...'; }

    var el = document.getElementById('ls-val-result');
    el.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary mb-3"></div><p class="text-muted">Running 7 validation checks...</p></div>';

    var res = await authFetch('/api/lead-sources/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            meta_source_id:   metaId   ? parseInt(metaId)   : null,
            google_source_id: googleId ? parseInt(googleId) : null,
        }),
    });
    if (btn) { btn.disabled = false; btn.textContent = '▶ Run Validation'; }

    var data = await res.json();
    if (!res.ok) {
        el.innerHTML = '<div class="alert alert-danger">' + _esc(data.error || 'Validation request failed') + '</div>';
        return;
    }

    var items = data.items || {};
    var allKeys = ['meta_connection','meta_lead_validation','google_connection','google_lead_validation','duplicate_detection','tenant_isolation','e2e_lms_flow'];
    var keyLabels = {
        meta_connection:       '1. Meta Connection',
        meta_lead_validation:  '2. Meta Lead Validation',
        google_connection:     '3. Google Connection',
        google_lead_validation:'4. Google Lead Validation',
        duplicate_detection:   '5. Duplicate Detection',
        tenant_isolation:      '6. Tenant Isolation',
        e2e_lms_flow:          '7. End-to-End LMS Flow',
    };

    var rows = allKeys.map(function(key) {
        var item = items[key] || { passed: false, result: 'FAIL', detail: 'Not run', sub: {} };
        var sub = item.sub || {};
        var subHtml = '';

        if (key === 'meta_connection') {
            subHtml = '<div class="d-flex gap-2 flex-wrap mt-1">' +
                _lsSubBadge('Login OK', sub.login_ok) +
                _lsSubBadge('Business Manager', sub.business_manager) +
                _lsSubBadge('Pages Visible', sub.pages_visible) +
                _lsSubBadge('Forms Visible', sub.forms_visible) +
                _lsSubBadge('Permissions OK', sub.permissions_ok) +
            '</div>';
        } else if (key === 'meta_lead_validation') {
            subHtml = '<div class="d-flex gap-2 flex-wrap mt-1">' +
                _lsSubBadge('Lead Entered LMS', sub.lead_entered_lms) +
                _lsSubBadge('Source Captured', sub.lead_source_captured) +
                _lsSubBadge('Campaign Captured', sub.campaign_captured) +
                _lsSubBadge('Lead Assigned', sub.lead_assigned) +
                _lsSubBadge('Timeline Created', sub.timeline_created) +
                _lsSubBadge('Push Notification', sub.push_notification_created) +
                _lsSubBadge('Action Board', sub.action_board_updated) +
            '</div>';
        } else if (key === 'google_connection') {
            subHtml = '<div class="d-flex gap-2 flex-wrap mt-1">' +
                _lsSubBadge('Login OK', sub.login_ok) +
                _lsSubBadge('Ads Account', sub.ads_account) +
                _lsSubBadge('Forms Visible', sub.forms_visible) +
                _lsSubBadge('Permissions OK', sub.permissions_ok) +
            '</div>';
        } else if (key === 'google_lead_validation') {
            subHtml = '<div class="d-flex gap-2 flex-wrap mt-1">' +
                _lsSubBadge('Lead Entered LMS', sub.lead_entered_lms) +
                _lsSubBadge('Lead Assigned', sub.lead_assigned) +
                _lsSubBadge('Timeline Created', sub.timeline_created) +
                _lsSubBadge('Push Notification', sub.push_notification_created) +
                _lsSubBadge('Action Board', sub.action_board_updated) +
            '</div>';
        } else if (key === 'duplicate_detection') {
            subHtml = '<div class="d-flex gap-2 flex-wrap mt-1">' +
                _lsSubBadge('Same Phone', sub.same_phone) +
                _lsSubBadge('Same Email', sub.same_email) +
                _lsSubBadge('Create Duplicate', sub.create_duplicate) +
                _lsSubBadge('Update Existing', sub.update_existing) +
                _lsSubBadge('Flag Duplicate', sub.flag_duplicate) +
            '</div>';
        } else if (key === 'tenant_isolation') {
            subHtml = sub.cross_lead_leaks !== undefined
                ? '<small class="text-muted">Lead leaks: ' + sub.cross_lead_leaks + ', Source leaks: ' + sub.cross_source_leaks + '</small>' : '';
        } else if (key === 'e2e_lms_flow') {
            subHtml = '<div class="d-flex gap-2 flex-wrap mt-1">' +
                _lsSubBadge('Meta Lead', sub.meta_lead) +
                _lsSubBadge('Assignment', sub.assignment) +
                _lsSubBadge('Notification', sub.notification) +
                _lsSubBadge('Action Board', sub.action_board) +
                _lsSubBadge('Lead Page', sub.lead_page) +
                _lsSubBadge('Activity Timeline', sub.activity_timeline) +
            '</div>';
        }

        return '<tr>' +
            '<td class="fw-semibold">' + (keyLabels[key] || key) + '</td>' +
            '<td><span class="badge fs-6 bg-' + (item.passed ? 'success' : 'danger') + '">' + item.result + '</span></td>' +
            '<td>' + (subHtml || '<small class="text-muted">' + _esc(item.detail || '') + '</small>') + '</td>' +
        '</tr>';
    }).join('');

    var ready = data.deployment_ready;
    var passCount = allKeys.filter(function(k) { return items[k] && items[k].passed; }).length;

    el.innerHTML =
        '<div class="alert alert-' + (ready ? 'success' : 'warning') + ' d-flex align-items-center mb-4">' +
            '<span class="fs-2 me-3">' + (ready ? '🚀' : '⚠️') + '</span>' +
            '<div><strong>' + _esc(data.summary || (passCount + '/7 checks passed')) + '</strong><br>' +
            '<span class="fs-5">Deployment Ready: <strong>' + (ready ? 'YES ✅' : 'NO ❌') + '</strong></span></div>' +
        '</div>' +
        '<table class="table table-bordered align-middle">' +
            '<thead class="table-light"><tr><th>Check</th><th style="width:90px">Result</th><th>Details</th></tr></thead>' +
            '<tbody>' + rows + '</tbody>' +
        '</table>' +
        '<p class="text-muted small">Validation run at: ' + _esc(data.run_at || '') + '</p>';
}

function _lsSubBadge(label, passed) {
    return '<span class="badge bg-' + (passed ? 'success' : 'danger') + ' text-wrap">' + _esc(label) + ' ' + (passed ? '✓' : '✗') + '</span>';
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB: Logs
// ══════════════════════════════════════════════════════════════════════════════

async function _lsLoadLogs(page) {
    if (!page) page = 1;
    _lsLogPage = page;
    var el = document.getElementById('ls-body');
    el.innerHTML = '<div class="text-center py-5 text-muted">Loading logs...</div>';

    var res = await authFetch('/api/lead-sources/logs?page=' + page + '&per_page=' + _lsLogPerPage);
    if (!res.ok) { el.innerHTML = '<p class="text-danger">Failed to load logs.</p>'; return; }
    var data = await res.json();
    _lsLogTotal = data.total || 0;

    function statusBadge(s) {
        var map = { processed: 'success', duplicate: 'warning text-dark', error: 'danger', queued: 'secondary' };
        var cls = map[s] || 'secondary';
        return '<span class="badge bg-' + cls + '">' + _esc(s) + '</span>';
    }

    var rows = (data.logs || []).map(function(l) {
        return '<tr>' +
            '<td>' + new Date(l.received_at).toLocaleString() + '</td>' +
            '<td>' + (SOURCE_TYPE_LABELS[l.source_type] || l.source_type) + '</td>' +
            '<td>' + _esc(l.campaign_name || '—') + '</td>' +
            '<td>' + statusBadge(l.status) + '</td>' +
            '<td>' + (l.lead_id ? '#' + l.lead_id : '—') + '</td>' +
            '<td class="text-muted small text-truncate" style="max-width:200px">' + _esc((l.error_message || '').substring(0, 80)) + '</td>' +
        '</tr>';
    }).join('') || '<tr><td colspan="6" class="text-center text-muted">No logs yet</td></tr>';

    var totalPages = Math.ceil(_lsLogTotal / _lsLogPerPage);
    var pageLinks = '';
    if (totalPages > 1) {
        var links = [];
        for (var i = 1; i <= Math.min(totalPages, 10); i++) {
            links.push('<li class="page-item ' + (i === page ? 'active' : '') + '"><a class="page-link" href="#" onclick="_lsLoadLogs(' + i + '); return false;">' + i + '</a></li>');
        }
        pageLinks = '<nav><ul class="pagination pagination-sm justify-content-center mt-3">' + links.join('') + '</ul></nav>';
    }

    el.innerHTML =
        '<table class="table table-sm table-hover align-middle"><thead class="table-light"><tr>' +
            '<th>Received</th><th>Platform</th><th>Campaign</th><th>Status</th><th>Lead</th><th>Error</th>' +
        '</tr></thead><tbody>' + rows + '</tbody></table>' +
        pageLinks +
        '<p class="text-muted text-center small">' + _lsLogTotal + ' total entries</p>';
}

// ══════════════════════════════════════════════════════════════════════════════
// TAB: Reports
// ══════════════════════════════════════════════════════════════════════════════

async function _lsLoadReports() {
    var el = document.getElementById('ls-body');
    el.innerHTML = '<div class="text-center py-5 text-muted">Loading reports...</div>';

    var results = await Promise.all([
        authFetch('/api/lead-sources/reports/by-source'),
        authFetch('/api/lead-sources/reports/by-campaign'),
    ]);
    var bySource   = results[0].ok   ? (await results[0].json()).rows || [] : [];
    var byCampaign = results[1].ok   ? (await results[1].json()).rows || [] : [];

    var srcRows = bySource.map(function(r) {
        return '<tr><td>' + _esc(r.source_name) + '</td><td>' + (SOURCE_TYPE_LABELS[r.source_type] || r.source_type) + '</td>' +
            '<td>' + r.total + '</td><td>' + r.created + '</td><td>' + r.duplicates + '</td>' +
            '<td>' + (r.errors ? '<span class="text-danger">' + r.errors + '</span>' : '0') + '</td></tr>';
    }).join('') || '<tr><td colspan="6" class="text-center text-muted">No data yet</td></tr>';

    var campRows = byCampaign.map(function(r) {
        return '<tr><td>' + _esc(r.campaign_name) + '</td><td>' + (SOURCE_TYPE_LABELS[r.source_type] || r.source_type) + '</td>' +
            '<td>' + r.total + '</td><td>' + r.created + '</td></tr>';
    }).join('') || '<tr><td colspan="4" class="text-center text-muted">No data yet</td></tr>';

    el.innerHTML = `
    <div class="row g-4">
        <div class="col-12">
            <h6>Leads by Source</h6>
            <table class="table table-sm table-bordered">
                <thead class="table-light"><tr><th>Source</th><th>Platform</th><th>Total</th><th>Created</th><th>Duplicates</th><th>Errors</th></tr></thead>
                <tbody>${srcRows}</tbody>
            </table>
        </div>
        <div class="col-12">
            <h6>Leads by Campaign</h6>
            <table class="table table-sm table-bordered">
                <thead class="table-light"><tr><th>Campaign</th><th>Platform</th><th>Total</th><th>Created</th></tr></thead>
                <tbody>${campRows}</tbody>
            </table>
        </div>
    </div>`;
}

// ══════════════════════════════════════════════════════════════════════════════
// Utilities
// ══════════════════════════════════════════════════════════════════════════════

function _esc(s) {
    if (s === null || s === undefined) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function _lsRelTime(iso) {
    if (!iso) return '—';
    var diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (diff < 60)    return diff + 's ago';
    if (diff < 3600)  return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return new Date(iso).toLocaleDateString();
}
