/**
 * Lead Sources - LMS Admin UI (Phase META-1.1)
 * ==========================================
 * Tabs:
 *   Sources     - list all sources, test/enable/disable
 *   Connect     - guided OAuth wizard (Meta and Google)
 *   Add/Edit    - manual credential form for webhooks/generic
 *   Test Lead   - inject synthetic lead through full pipeline
 *   Validate    - run 7-item PASS/FAIL validation report
 *   Logs        - paginated ingestion log
 *   Reports     - by-source and by-campaign tables
 *
 * Depends on: authFetch() from auth.js, showToast() from ui-utils.js
 */

// Constants

const SOURCE_TYPE_LABELS = {
    meta:            'Facebook / Instagram',
    google:          'Google Lead Form',
    webhook:         'Website / Webhook',
    housing:         'Housing.com',
    magicbricks:     'MagicBricks',
    ninetynineacres: '99acres',
    indiamart:       'IndiaMART',
    whatsapp_form:   'WhatsApp Form',
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

// Module state

let _lsTab     = 'sources';
let _lsEditId  = null;
let _lsSources = [];
let _lsArchivedSources = [];
let _lsSourcesLoaded = false;
let _lsLogPage = 1;
let _lsLogTotal = 0;
const _lsLogPerPage = 25;
let _lsTierRunId = null;
let _lsTierAutoRunning = false;
let _lsSourceFilters = {
    query: '',
    status: 'all',
    type: 'all',
    health: 'all',
};

// OAuth wizard state
let _metaWizard   = {};
let _googleWizard = {};

const _LS_META_WIZARD_STORAGE_KEY = 'ls_meta_wizard';
const _LS_GOOGLE_WIZARD_STORAGE_KEY = 'ls_google_wizard';

function _lsPersistMetaWizard() {
    try {
        sessionStorage.setItem(_LS_META_WIZARD_STORAGE_KEY, JSON.stringify(_metaWizard || {}));
    } catch (_err) {}
}

function _lsLoadPersistedMetaWizard() {
    try {
        var raw = sessionStorage.getItem(_LS_META_WIZARD_STORAGE_KEY);
        if (!raw) return null;
        var data = JSON.parse(raw);
        return data && typeof data === 'object' ? data : null;
    } catch (_err) {
        return null;
    }
}

function _lsClearPersistedMetaWizard() {
    try {
        sessionStorage.removeItem(_LS_META_WIZARD_STORAGE_KEY);
    } catch (_err) {}
}

function _lsPersistGoogleWizard() {
    try {
        sessionStorage.setItem(_LS_GOOGLE_WIZARD_STORAGE_KEY, JSON.stringify(_googleWizard || {}));
    } catch (_err) {}
}

function _lsLoadPersistedGoogleWizard() {
    try {
        var raw = sessionStorage.getItem(_LS_GOOGLE_WIZARD_STORAGE_KEY);
        if (!raw) return null;
        var data = JSON.parse(raw);
        return data && typeof data === 'object' ? data : null;
    } catch (_err) {
        return null;
    }
}

function _lsClearPersistedGoogleWizard() {
    try {
        sessionStorage.removeItem(_LS_GOOGLE_WIZARD_STORAGE_KEY);
    } catch (_err) {}
}

async function _lsReadJsonSafe(res) {
    try {
        return await res.json();
    } catch (_err) {
        return {};
    }
}

async function _lsApiErrorMessage(res, fallback) {
    var data = await _lsReadJsonSafe(res);
    return (data && (data.error || data.message)) || fallback;
}

async function _lsEnsureSourcesLoaded() {
    if (_lsSourcesLoaded) return true;
    try {
        var res = await authFetch('/api/lead-sources');
        if (!res.ok) {
            showToast(await _lsApiErrorMessage(res, 'Failed to load sources.'), 'danger');
            return false;
        }
        var data = await _lsReadJsonSafe(res);
        _lsSources = (data.sources || []).filter(function(s) { return s && s.is_active !== false; });
        _lsSourcesLoaded = true;
        return true;
    } catch (err) {
        showToast((err && err.message) || 'Failed to load sources.', 'danger');
        return false;
    }
}

async function _lsOpenTestLeadTab() {
    var ok = await _lsEnsureSourcesLoaded();
    if (!ok) return;
    _lsRenderTestLead();
}

async function _lsOpenValidateTab() {
    var ok = await _lsEnsureSourcesLoaded();
    if (!ok) return;
    _lsRenderValidate();
}

// Entry Point

function renderLeadSources() {
    const el = document.getElementById('content');
    if (!el) return;

    el.innerHTML = `
    <div class="page-header d-flex align-items-center justify-content-between mb-3">
        <div>
            <h2 class="mb-0">Lead Sources</h2>
            <p class="text-muted mb-0 small">Manage LMS lead ingestion across Meta, Google, website forms and partner channels.</p>
        </div>
    </div>

    <ul class="nav nav-tabs mb-4" id="ls-tabs">
        <li class="nav-item"><a class="nav-link active" href="#" data-tab="sources">Sources</a></li>
        <li class="nav-item"><a class="nav-link" href="#" data-tab="archived">Archived</a></li>
        <li class="nav-item"><a class="nav-link" href="#" data-tab="connect">+ Connect</a></li>
        <li class="nav-item"><a class="nav-link" href="#" data-tab="add">Manual / Webhook</a></li>
        <li class="nav-item"><a class="nav-link" href="#" data-tab="testlead">Test Lead</a></li>
        <li class="nav-item"><a class="nav-link" href="#" data-tab="validate">Validate</a></li>
        <li class="nav-item"><a class="nav-link" href="#" data-tab="tiertest">Tier Test</a></li>
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

    // Auto-switch to connect tab if returning from OAuth callback
    var urlParams = new URLSearchParams(window.location.search);
    var persistedMetaWizard = _lsLoadPersistedMetaWizard();
    var persistedGoogleWizard = _lsLoadPersistedGoogleWizard();
    var startTab = (
        urlParams.get('meta_session') ||
        urlParams.get('google_session') ||
        urlParams.get('meta_tab') === 'connect' ||
        (persistedMetaWizard && persistedMetaWizard.step >= 3) ||
        (persistedGoogleWizard && persistedGoogleWizard.step >= 2)
    ) ? 'connect' : 'sources';
    _lsRenderTab(startTab);
    if (startTab === 'connect') {
        document.querySelectorAll('#ls-tabs .nav-link').forEach(function(a) {
            a.classList.toggle('active', a.dataset.tab === 'connect');
        });
    }
}

function _lsEventButton(evt) {
    if (!evt || !evt.target) return null;
    return evt.target.closest ? evt.target.closest('button') : evt.target;
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
    if (tab === 'archived') return _lsLoadArchivedSources();
    if (tab === 'connect')  return _lsRenderConnect();
    if (tab === 'add')      return _lsRenderForm(null);
    if (tab === 'testlead') return _lsOpenTestLeadTab();
    if (tab === 'validate') return _lsOpenValidateTab();
    if (tab === 'tiertest') return _lsRenderTierTest();
    if (tab === 'logs')     return _lsLoadLogs(1);
    if (tab === 'reports')  return _lsLoadReports();
}

// Sources Tab

async function _lsLoadSources() {
    const el = document.getElementById('ls-body');
    el.innerHTML = '<div class="text-center py-5 text-muted">Loading...</div>';
    try {
        const res = await authFetch('/api/lead-sources');
        if (!res.ok) {
            el.innerHTML = '<p class="text-danger">' + _esc(await _lsApiErrorMessage(res, 'Failed to load sources.')) + '</p>';
            return;
        }
        const data = await _lsReadJsonSafe(res);
        _lsSources = (data.sources || []).filter(function(s) { return s && s.is_active !== false; });
        _lsSourcesLoaded = true;
    } catch (err) {
        el.innerHTML = '<p class="text-danger">' + _esc((err && err.message) || 'Failed to load sources.') + '</p>';
        return;
    }
    _lsRenderSources();
}

async function _lsLoadArchivedSources() {
    const el = document.getElementById('ls-body');
    el.innerHTML = '<div class="text-center py-5 text-muted">Loading...</div>';
    try {
        const res = await authFetch('/api/lead-sources?include_inactive=true');
        if (!res.ok) {
            el.innerHTML = '<p class="text-danger">' + _esc(await _lsApiErrorMessage(res, 'Failed to load archived sources.')) + '</p>';
            return;
        }
        const data = await _lsReadJsonSafe(res);
        _lsArchivedSources = (data.sources || []).filter(function(s) { return s && s.is_active === false; });
    } catch (err) {
        el.innerHTML = '<p class="text-danger">' + _esc((err && err.message) || 'Failed to load archived sources.') + '</p>';
        return;
    }
    _lsRenderArchivedSources();
}

function _lsRenderSources() {
    const el = document.getElementById('ls-body');
    if (!_lsSources.length) {
        el.innerHTML = `
        <div class="text-center py-5 border rounded bg-white">
            <h4 class="mb-2">Connect Your First Lead Source</h4>
            <p class="text-muted mb-3">Automatically capture leads from Meta, Google, websites, and other channels.</p>
            <button class="btn btn-primary me-2" onclick="_lsSwitchTab('connect')">Connect Meta</button>
            <button class="btn btn-outline-secondary" onclick="_lsSwitchTab('add')">+ Manual / Webhook</button>
        </div>`;
        return;
    }

    var types = Object.keys(SOURCE_TYPE_LABELS).map(function(k) {
        return '<option value="' + _esc(k) + '">' + _esc(SOURCE_TYPE_LABELS[k]) + '</option>';
    }).join('');

    el.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
        <div>
            <h5 class="mb-1">Connected Sources</h5>
            <span class="text-muted small">${_lsSources.length} source(s) configured</span>
        </div>
        <div>
            <button class="btn btn-primary btn-sm me-2" onclick="_lsSwitchTab('connect')">Connect New</button>
            <button class="btn btn-outline-secondary btn-sm" onclick="_lsSwitchTab('add')">+ Manual</button>
        </div>
    </div>
    <div class="row g-2 mb-3">
        <div class="col-md-4"><input id="ls-source-filter-query" class="form-control form-control-sm" placeholder="Search source, account, or page"></div>
        <div class="col-md-3"><select id="ls-source-filter-status" class="form-select form-select-sm"><option value="all">All statuses</option><option value="active">Active</option><option value="disabled">Disabled</option></select></div>
        <div class="col-md-3"><select id="ls-source-filter-type" class="form-select form-select-sm"><option value="all">All types</option>${types}</select></div>
        <div class="col-md-2"><select id="ls-source-filter-health" class="form-select form-select-sm"><option value="all">All health</option><option value="connected">Connected</option><option value="warning">Warning</option><option value="error">Error</option></select></div>
    </div>
    <div id="ls-source-card-grid" class="row g-3"></div>`;

    _lsRenderSourceCards();
    _lsBindSourceFilters();
}

function _lsRenderArchivedSources() {
    const el = document.getElementById('ls-body');
    if (!_lsArchivedSources.length) {
        el.innerHTML = '<div class="text-center py-5 border rounded bg-white"><h4 class="mb-2">No Archived Sources</h4><p class="text-muted mb-0">Disabled or disconnected sources appear here for cleanup and restore.</p></div>';
        return;
    }

    el.innerHTML =
        '<div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">' +
            '<div><h5 class="mb-1">Archived Sources</h5><span class="text-muted small">' + _lsArchivedSources.length + ' source(s) archived</span></div>' +
            '<div><button class="btn btn-outline-secondary btn-sm" onclick="_lsSwitchTab(\'sources\')">Back to Active Sources</button></div>' +
        '</div>' +
        '<div class="row g-3" id="ls-archived-card-grid"></div>';

    var host = document.getElementById('ls-archived-card-grid');
    host.innerHTML = _lsArchivedSources.map(function(s) {
        return '<div class="col-xl-4 col-md-6">' +
            '<div class="card h-100 shadow-sm border">' +
                '<div class="card-body d-flex flex-column">' +
                    '<div class="d-flex justify-content-between align-items-start mb-2">' +
                        '<div><h6 class="mb-1">' + _esc(s.name || 'Unnamed Source') + '</h6><div class="text-muted small">' + _esc(SOURCE_TYPE_LABELS[s.source_type] || s.source_type || 'Source') + '</div></div>' +
                        '<span class="badge bg-secondary">Archived</span>' +
                    '</div>' +
                    '<div class="small mb-3">' +
                        '<div>Total Leads: ' + (s.total_leads_ingested || 0) + '</div>' +
                        '<div>Last Lead: ' + (s.last_lead_at ? _lsRelTime(s.last_lead_at) : 'No lead yet') + '</div>' +
                        '<div>Last Updated: ' + (s.updated_at ? _lsRelTime(s.updated_at) : 'N/A') + '</div>' +
                    '</div>' +
                    '<div class="mt-auto d-flex flex-wrap gap-1">' +
                        '<button class="btn btn-sm btn-outline-secondary" onclick="_lsOpenSourceDetails(' + s.id + ')">View Details</button>' +
                        '<button class="btn btn-sm btn-outline-success" onclick="_lsRestoreSource(' + s.id + ')">Restore</button>' +
                    '</div>' +
                '</div>' +
            '</div>' +
        '</div>';
    }).join('');
}

function _lsSourceHealthState(s) {
    if (!s.is_active) return 'disabled';
    if (s.permission_status === 'error') return 'error';
    if (s.permission_status === 'partial') return 'warning';
    return 'connected';
}

function _lsFilteredSources() {
    return _lsSources.filter(function(s) {
        var q = String(_lsSourceFilters.query || '').trim().toLowerCase();
        var type = _lsSourceFilters.type || 'all';
        var status = _lsSourceFilters.status || 'all';
        var health = _lsSourceFilters.health || 'all';
        var hay = [s.name || '', s.connected_account || '', (s.credentials || {}).page_id || ''].join(' ').toLowerCase();
        if (q && hay.indexOf(q) === -1) return false;
        if (type !== 'all' && s.source_type !== type) return false;
        if (status === 'active' && !s.is_active) return false;
        if (status === 'disabled' && s.is_active) return false;
        if (health !== 'all' && _lsSourceHealthState(s) !== health) return false;
        return true;
    });
}

function _lsRenderSourceCards() {
    var host = document.getElementById('ls-source-card-grid');
    if (!host) return;

    var items = _lsFilteredSources();
    if (!items.length) {
        host.innerHTML = '<div class="col-12"><div class="alert alert-light border">No sources match current filters.</div></div>';
        return;
    }

    host.innerHTML = items.map(function(s) {
        var creds = s.credentials || {};
        var formCount = Array.isArray(s.available_forms) ? s.available_forms.length : 0;
        var pageCount = creds.page_id ? 1 : 0;
        var health = _lsSourceHealthState(s);
        var healthCls = health === 'connected' ? 'success' : (health === 'warning' ? 'warning text-dark' : (health === 'error' ? 'danger' : 'secondary'));
        var healthText = health === 'connected' ? 'Connected' : (health === 'warning' ? 'Warning' : (health === 'error' ? 'Error' : 'Disabled'));
        var canDisconnect = (s.source_type === 'meta' || s.source_type === 'google');

        return '<div class="col-xl-4 col-md-6">' +
            '<div class="card h-100 shadow-sm border-0">' +
                '<div class="card-body d-flex flex-column">' +
                    '<div class="d-flex justify-content-between align-items-start mb-2">' +
                        '<div><h6 class="mb-1">' + _esc(s.name || 'Unnamed Source') + '</h6><div class="text-muted small">' + _esc(SOURCE_TYPE_LABELS[s.source_type] || s.source_type || 'Source') + '</div></div>' +
                        '<span class="badge bg-' + healthCls + '">' + healthText + '</span>' +
                    '</div>' +
                    '<div class="small mb-2"><div class="text-muted">Connected Assets</div>' +
                        '<div>Account: ' + _esc(s.connected_account || 'Not linked') + '</div>' +
                        '<div>Pages: ' + pageCount + ' | Forms: ' + formCount + '</div>' +
                    '</div>' +
                    '<div class="small mb-3"><div class="text-muted">Metrics</div>' +
                        '<div>Total Leads: ' + (s.total_leads_ingested || 0) + '</div>' +
                        '<div>Last Lead: ' + (s.last_lead_at ? _lsRelTime(s.last_lead_at) : 'No lead yet') + '</div>' +
                        '<div>Last Sync: ' + (s.last_tested_at ? _lsRelTime(s.last_tested_at) : 'Not tested') + '</div>' +
                    '</div>' +
                    '<div class="mt-auto d-flex flex-wrap gap-1">' +
                        '<button class="btn btn-sm btn-outline-secondary" onclick="_lsOpenSourceDetails(' + s.id + ')">View Details</button>' +
                        '<button class="btn btn-sm btn-outline-primary" onclick="_lsTestSource(' + s.id + ', event)">Test Connection</button>' +
                        '<button class="btn btn-sm btn-outline-info" onclick="_lsOpenEdit(' + s.id + ')">Edit Source</button>' +
                        '<button class="btn btn-sm btn-outline-danger" onclick="_lsDeleteSource(' + s.id + ')">Remove</button>' +
                        (canDisconnect ? '<button class="btn btn-sm btn-outline-danger" onclick="_lsDisconnectSource(' + s.id + ')">Disconnect</button>' : '') +
                        '<button class="btn btn-sm ' + (s.is_active ? 'btn-outline-warning' : 'btn-outline-success') + '" onclick="_lsToggleSource(' + s.id + ', ' + (!s.is_active) + ')">' + (s.is_active ? 'Disable' : 'Enable') + '</button>' +
                    '</div>' +
                '</div>' +
            '</div>' +
        '</div>';
    }).join('');
}

function _lsBindSourceFilters() {
    var query = document.getElementById('ls-source-filter-query');
    var status = document.getElementById('ls-source-filter-status');
    var type = document.getElementById('ls-source-filter-type');
    var health = document.getElementById('ls-source-filter-health');
    if (!query || !status || !type || !health) return;

    query.value = _lsSourceFilters.query;
    status.value = _lsSourceFilters.status;
    type.value = _lsSourceFilters.type;
    health.value = _lsSourceFilters.health;

    [query, status, type, health].forEach(function(el) {
        el.addEventListener('input', function() {
            _lsSourceFilters.query = query.value || '';
            _lsSourceFilters.status = status.value || 'all';
            _lsSourceFilters.type = type.value || 'all';
            _lsSourceFilters.health = health.value || 'all';
            _lsRenderSourceCards();
        });
        el.addEventListener('change', function() {
            _lsSourceFilters.query = query.value || '';
            _lsSourceFilters.status = status.value || 'all';
            _lsSourceFilters.type = type.value || 'all';
            _lsSourceFilters.health = health.value || 'all';
            _lsRenderSourceCards();
        });
    });
}

async function _lsTestSource(id, evt) {
    var btn = _lsEventButton(evt) || document.querySelector('[onclick*="_lsTestSource(' + id + '"]');
    if (btn) { btn.disabled = true; btn.textContent = 'Checking...'; }
    var res = await authFetch('/api/lead-sources/' + id + '/test', { method: 'POST' });
    if (btn) { btn.disabled = false; btn.textContent = 'Test Connection'; }
    var data = await res.json();
    var t = data.test || {};
    var label = t.result === 'pass' ? 'PASS' : t.result === 'partial' ? 'PARTIAL' : 'FAIL';
    var icon = t.result === 'pass' ? 'OK' : t.result === 'partial' ? 'WARN' : 'ERR';
    var tone = t.result === 'pass' ? 'success' : (t.result === 'partial' ? 'warning' : 'danger');
    showToast('Ping (connection check): ' + label + ' - ' + (t.message || 'Check completed') + ' [' + icon + ']', tone);
    await _lsLoadSources();
}

async function _lsToggleSource(id, enable) {
    var res = await authFetch('/api/lead-sources/' + id + '/' + (enable ? 'enable' : 'disable'), { method: 'POST' });
    if (!res.ok) { showToast('Failed to update source', 'danger'); return; }
    showToast(enable ? 'Source enabled' : 'Source disabled', 'success');
    await _lsLoadSources();
}

    async function _lsDisconnectSource(id) {
        if (!confirm('Disconnect this account from the source?')) return;
        var res = await authFetch('/api/lead-sources/' + id + '/disconnect', { method: 'POST' });
        if (!res.ok) {
            var msg = await _lsApiErrorMessage(res, 'Disconnect failed');
            msg = 'Disconnect failed (HTTP ' + res.status + '): ' + msg;
            showToast(msg, 'danger');
            return;
        }
        showToast('Source disconnected', 'success');
        _lsLoadSources();
    }

function _lsOpenEdit(id) {
    _lsEditId = id;
    var source = _lsSources.find(function(s) { return s.id === id; }) || _lsArchivedSources.find(function(s) { return s.id === id; });
    _lsSwitchTab('add');
    if (source) _lsRenderForm(source);
}

async function _lsRestoreSource(id) {
    var res = await authFetch('/api/lead-sources/' + id + '/enable', { method: 'POST' });
    if (!res.ok) {
        showToast(await _lsApiErrorMessage(res, 'Restore failed'), 'danger');
        return;
    }
    showToast('Source restored', 'success');
    await _lsLoadArchivedSources();
}

function _lsCloseSourceDetails() {
    var modal = document.getElementById('lsSourceDetailsModal');
    if (modal) modal.remove();
}

function _lsSourceDetailsFormsHtml(forms, mode, errorMessage) {
    var list = Array.isArray(forms) ? forms : [];
    var headerNote = mode === 'live'
        ? 'Live forms currently available on this Meta page.'
        : mode === 'saved'
            ? 'Saved forms currently attached to this source.'
            : 'Loading current Meta forms...';

    var errorHtml = errorMessage
        ? '<div class="alert alert-warning py-2 small mb-3">' + _esc(errorMessage) + '</div>'
        : '';

    if (!list.length && mode === 'loading') {
        return errorHtml + '<div class="text-muted">Loading forms...</div>';
    }

    if (!list.length) {
        return errorHtml + '<div class="text-muted">No forms are currently available for this source.</div>';
    }

    var items = list.map(function(form) {
        var status = form && form.status ? '<span class="badge bg-secondary ms-2">' + _esc(form.status) + '</span>' : '';
        var leads = form && typeof form.leads_count !== 'undefined' && form.leads_count !== null
            ? '<small class="text-muted d-block mt-1">Leads: ' + _esc(String(form.leads_count)) + '</small>'
            : '';
        return '<div class="list-group-item">' +
            '<div class="d-flex justify-content-between align-items-start gap-3">' +
                '<div><strong>' + _esc((form && form.name) || 'Unnamed form') + '</strong><br><small class="text-muted">Form ID: ' + _esc((form && form.id) || '') + '</small>' + leads + '</div>' +
                '<div>' + status + '</div>' +
            '</div>' +
        '</div>';
    }).join('');

    return errorHtml + '<div class="small text-muted mb-3">' + headerNote + '</div><div class="list-group list-group-flush">' + items + '</div>';
}

function _lsRenderSourceDetailsForms(forms, mode, errorMessage) {
    var body = document.getElementById('ls-source-details-forms-body');
    var count = document.getElementById('ls-source-details-forms-count');
    if (body) body.innerHTML = _lsSourceDetailsFormsHtml(forms, mode, errorMessage);
    if (count) count.textContent = (Array.isArray(forms) ? forms.length : 0) + ' form(s)';
}

async function _lsLoadLiveSourceForms(source) {
    if (!source || source.source_type !== 'meta') return;
    var creds = source.credentials || {};
    if (!creds.page_id || !(creds.page_access_token || creds.access_token)) {
        _lsRenderSourceDetailsForms(source.available_forms || [], 'saved', 'Live page details are unavailable for this source, showing saved forms only.');
        return;
    }

    _lsRenderSourceDetailsForms(source.available_forms || [], 'loading', 'Loading current forms from Meta...');

    try {
        var data = await _apiRequest('/lead-sources/meta/page-forms', {
            method: 'POST',
            headers: _apiJsonHeaders(_apiAuthHeaders()),
            body: JSON.stringify({
                page_id: creds.page_id,
                page_access_token: creds.page_access_token || creds.access_token || '',
                user_access_token: creds.user_token || ''
            }),
            retries: 0,
            timeoutMs: 15000,
        });
        _lsRenderSourceDetailsForms(data.forms || [], 'live');
    } catch (err) {
        var message = (err && err.message) || 'Could not load current Meta forms.';
        _lsRenderSourceDetailsForms(source.available_forms || [], 'saved', message + ' Showing saved forms instead.');
    }
}

function _lsOpenSourceDetails(id) {
    var source = _lsSources.find(function(s) { return s.id === id; }) || _lsArchivedSources.find(function(s) { return s.id === id; });
    if (!source) {
        showToast('Source not found', 'danger');
        return;
    }

    _lsCloseSourceDetails();

    var overlay = document.createElement('div');
    overlay.id = 'lsSourceDetailsModal';
    overlay.className = 'modal-overlay';
    overlay.innerHTML = _lsSourceDetailsModalHtml(source);
    overlay.addEventListener('click', function(evt) {
        if (evt.target === overlay) _lsCloseSourceDetails();
    });
    document.body.appendChild(overlay);
    _lsLoadLiveSourceForms(source);
}

function _lsSourceDetailsModalHtml(source) {
    var forms = Array.isArray(source.available_forms) ? source.available_forms : [];
    var creds = source.credentials || {};
    var pageId = creds.page_id || '—';
    var account = source.connected_account || '—';
    var formsHtml = _lsSourceDetailsFormsHtml(forms, 'saved');

    return '<div class="modal-box" style="max-width:760px;width:96%;max-height:90vh;overflow:auto;">' +
        '<div class="d-flex justify-content-between align-items-center mb-3">' +
            '<div><h5 class="mb-1">' + _esc(source.name) + '</h5><div class="text-muted small">Saved source details and connected forms</div></div>' +
            '<button type="button" class="btn btn-outline-secondary btn-sm" onclick="_lsCloseSourceDetails()">Close</button>' +
        '</div>' +
        '<div class="card mb-3">' +
            '<div class="card-body">' +
                '<div class="row g-3">' +
                    '<div class="col-md-4"><div class="small text-muted">Platform</div><div>' + _esc(SOURCE_TYPE_LABELS[source.source_type] || source.source_type) + '</div></div>' +
                    '<div class="col-md-4"><div class="small text-muted">Connected Account</div><div>' + _esc(account) + '</div></div>' +
                    '<div class="col-md-4"><div class="small text-muted">Page ID</div><div>' + _esc(pageId) + '</div></div>' +
                '</div>' +
            '</div>' +
        '</div>' +
        '<div class="card">' +
            '<div class="card-header d-flex justify-content-between align-items-center">' +
                '<strong>Connected Forms</strong>' +
                '<span class="badge bg-primary-subtle text-primary border" id="ls-source-details-forms-count">' + forms.length + ' form(s)</span>' +
            '</div>' +
            '<div class="card-body" id="ls-source-details-forms-body">' + formsHtml + '</div>' +
        '</div>' +
    '</div>';
}

function _lsRenderConnectedFormsPanel(source) {
    if (!source || !Array.isArray(source.available_forms) || !source.available_forms.length) return '';
    var items = source.available_forms.map(function(form) {
        var status = form && form.status ? '<span class="badge bg-secondary ms-2">' + _esc(form.status) + '</span>' : '';
        var leads = form && typeof form.leads_count !== 'undefined' && form.leads_count !== null
            ? '<small class="text-muted ms-2">Leads: ' + _esc(String(form.leads_count)) + '</small>'
            : '';
        return '<div class="list-group-item d-flex justify-content-between align-items-start gap-3">' +
            '<div><strong>' + _esc((form && form.name) || 'Unnamed form') + '</strong><br><small class="text-muted">ID: ' + _esc((form && form.id) || '') + '</small></div>' +
            '<div class="text-end">' + status + leads + '</div>' +
        '</div>';
    }).join('');

    return '<div class="card mb-3">' +
        '<div class="card-header d-flex justify-content-between align-items-center">' +
            '<strong>Connected Forms</strong>' +
            '<span class="badge bg-primary-subtle text-primary border">' + source.available_forms.length + ' saved</span>' +
        '</div>' +
        '<div class="card-body">' +
            '<div class="small text-muted mb-3">These are the forms currently saved to this source.</div>' +
            '<div class="list-group list-group-flush">' + items + '</div>' +
        '</div>' +
    '</div>';
}

function _lsOpenTestLead(id) {
    _lsSwitchTab('testlead');
    setTimeout(function() {
        var sel = document.getElementById('ls-test-source-id');
        if (sel) sel.value = id;
    }, 120);
}

// ==============================================================================
// TAB: Connect - guided OAuth wizard chooser
// ==============================================================================

function _lsRenderConnect() {
    var el = document.getElementById('ls-body');
    // Check if returning from OAuth
    var urlParams = new URLSearchParams(window.location.search);
    var metaSession   = urlParams.get('meta_session');
    var googleSession = urlParams.get('google_session');
    var persistedMetaWizard = _lsLoadPersistedMetaWizard();
    var persistedGoogleWizard = _lsLoadPersistedGoogleWizard();
    if (metaSession || googleSession) {
        el.innerHTML = `<div class="row g-4"><div class="col-12"><div id="ls-wizard-area"></div></div></div>`;
        if (metaSession)   _lsStartMetaWizard();
        if (googleSession) _lsStartGoogleWizard();
        return;
    }
    if (persistedGoogleWizard && persistedGoogleWizard.step >= 2) {
        el.innerHTML = `<div class="row g-4"><div class="col-12"><div id="ls-wizard-area"></div></div></div>`;
        _lsStartGoogleWizard();
        return;
    }
    if (persistedMetaWizard && persistedMetaWizard.step >= 3) {
        el.innerHTML = `<div class="row g-4"><div class="col-12"><div id="ls-wizard-area"></div></div></div>`;
        _lsStartMetaWizard();
        return;
    }
    el.innerHTML = `
    <div class="row g-4">
        <div class="col-md-5">
            <div class="card h-100">
                <div class="card-body">
                    <h5 class="card-title">Connect Meta (Facebook / Instagram)</h5>
                    <p class="card-text text-muted small">Guided OAuth wizard. Select your page and lead forms.</p>
                    <ul class="text-muted small mb-3">
                        <li>Enter App credentials</li>
                        <li>Exchange access token</li>
                        <li>Select Page</li>
                        <li>Select Lead Forms</li>
                        <li>Save &amp; Activate</li>
                    </ul>
                    <button class="btn btn-primary w-100 mb-2" onclick="_lsStartMetaWizard()">Connect Meta</button>
                    <button class="btn btn-outline-danger w-100" onclick="_lsDisconnectExistingMetaSource()">Disconnect Existing Meta Connection</button>
                </div>
            </div>
        </div>
        <div class="col-md-5">
            <div class="card h-100">
                <div class="card-body">
                    <h5 class="card-title">Connect Google Lead Form</h5>
                    <p class="card-text text-muted small">OAuth 2.0 connection. Receive leads from Google Ads Lead Form extensions.</p>
                    <ul class="text-muted small mb-3">
                        <li>Enter OAuth credentials</li>
                        <li>Authorize Google Account</li>
                        <li>Configure Customer ID</li>
                        <li>Save &amp; Activate</li>
                    </ul>
                    <button class="btn btn-danger w-100" onclick="_lsStartGoogleWizard()">Connect Google</button>
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

// --- META WIZARD ---------------------------------------------------------------

function _lsStartMetaWizard(forceFresh) {
    // Check if returning from OAuth callback
    var urlParams = new URLSearchParams(window.location.search);
    var sessionKey = urlParams.get('meta_session');
    var persistedMetaWizard = _lsLoadPersistedMetaWizard();
    if (!forceFresh && sessionKey) {
        _metaWizard = { step: 3, sessionKey: sessionKey, pages: [], pagesLoaded: false, selectedPage: null, forms: [], selectedForms: [], user: null, longToken: '' };
        _lsPersistMetaWizard();
        _lsRenderMetaWizard();
        _lsMetaLoadSession(sessionKey);
        return;
    }
    if (!forceFresh && persistedMetaWizard && persistedMetaWizard.step >= 3) {
        _metaWizard = Object.assign({ pages: [], pagesLoaded: false, selectedPage: null, forms: [], selectedForms: [] }, persistedMetaWizard);
        _lsRenderMetaWizard();
        if (_metaWizard.sessionKey && (!_metaWizard.pagesLoaded || !_metaWizard.user)) {
            _lsMetaLoadSession(_metaWizard.sessionKey);
        }
        return;
    }

    if (forceFresh) {
        var cleanUrl = window.location.pathname;
        window.history.replaceState({}, '', cleanUrl + '?meta_tab=connect');
    }

    _metaWizard = { step: 1, businessId: '', sessionKey: '', pages: [], pagesLoaded: false, selectedPage: null, forms: [], selectedForms: [], user: null, longToken: '' };
    _lsClearPersistedMetaWizard();
    _lsRenderMetaWizard();
}

async function _lsMetaLoadSession(sessionKey) {
    var el = document.getElementById('ls-wizard-area');
    var data;
    try {
        data = await _apiRequest('/lead-sources/meta/auth-session/' + encodeURIComponent(sessionKey), {
            headers: _apiAuthHeaders(),
            retries: 0,
            timeoutMs: 15000,
        });
    } catch (err) {
        _lsClearPersistedMetaWizard();
        var cleanUrl = window.location.pathname;
        window.history.replaceState({}, '', cleanUrl + '?meta_tab=connect');
        if (el) el.innerHTML = '<div class="alert alert-danger">' + _esc((err && err.message) || 'Session expired') + ' — <a href="#" onclick="event.preventDefault();_lsStartMetaWizard(true)">Start over</a></div>';
        return;
    }
    _metaWizard.user      = data.user;
    _metaWizard.pages     = data.pages || [];
    _metaWizard.pagesLoaded = true;
    _metaWizard.longToken = data.long_token || '';
    _metaWizard.businessId = data.business_id || _metaWizard.businessId || '';
    _metaWizard.step      = 3;
    _lsPersistMetaWizard();
    // Clean the URL
    var cleanUrl = window.location.pathname;
    window.history.replaceState({}, '', cleanUrl + '?meta_tab=connect');
    _lsRenderMetaWizard();
}

function _lsRenderMetaWizard() {
    var el = document.getElementById('ls-wizard-area');
    if (!el) return;
    var w = _metaWizard;

    var stepLabels = ['Business ID', 'Login', 'Select Page', 'Select Forms', 'Save'];
    var stepNav = stepLabels.map(function(s, i) {
        var cls = (i + 1 === w.step) ? 'bg-primary' : (i + 1 < w.step) ? 'bg-success' : 'bg-secondary';
        return '<span class="badge ' + cls + ' me-1">' + (i + 1 < w.step ? 'Done' : (i + 1)) + '. ' + s + '</span>';
    }).join('');

    var body = '';

    if (w.step === 1) {
        body = `
        <p class="text-muted small">Enter your Facebook Business ID. You can find this in <strong>Facebook Business Manager -> Settings -> Business Info</strong>.</p>
        <div class="mb-3">
            <label class="form-label fw-semibold">Meta Business ID</label>
            <input class="form-control" id="mw-business-id" placeholder="e.g. 123456789012345" value="${_esc(w.businessId)}">
            <div class="form-text">This is your Business Portfolio ID from Meta Business Manager.</div>
        </div>
        <button class="btn btn-primary" onclick="_lsMetaStep1Next(event)">Next</button>`;

    } else if (w.step === 2) {
        body = `
        <p class="text-muted small">Click the button below to log in with the Facebook account that manages your Business ID <strong>${_esc(w.businessId)}</strong>.</p>
        <div class="d-grid gap-2 mb-3" style="max-width:300px">
            <button class="btn btn-primary btn-lg" onclick="_lsMetaOpenFacebookLogin(event)">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="white" class="me-2"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>
                Login with Facebook
            </button>
        </div>
        <p class="text-muted small">You will be redirected to Facebook to authorize access. After approving, you'll be brought back here automatically.</p>
        <button class="btn btn-outline-secondary btn-sm" onclick="_metaWizard.step=1; _lsRenderMetaWizard()"><- Back</button>`;

    } else if (w.step === 3) {
        if (!w.pagesLoaded) {
            body = '<div class="text-center py-4"><div class="spinner-border text-primary mb-3"></div><p class="text-muted">Loading your Facebook Pages...</p></div>';
        } else if (!w.pages || !w.pages.length) {
            body =
                '<div class="alert alert-warning mb-3">No Facebook Pages were returned for this account/business.</div>' +
                '<p class="text-muted small mb-3">Check that the logged-in Facebook user has access to at least one Page under the selected Business and has granted required permissions.</p>' +
                '<div class="d-flex gap-2">' +
                    '<button class="btn btn-outline-secondary btn-sm" onclick="_lsStartMetaWizard(true)">Start Over</button>' +
                    '<button class="btn btn-outline-primary btn-sm" onclick="_metaWizard.step=1; _lsRenderMetaWizard()">Change Business ID</button>' +
                '</div>';
        } else {
            var pageItems = w.pages.map(function(p) {
                var active = (w.selectedPage && w.selectedPage.id === p.id) ? 'active' : '';
                return '<div class="list-group-item list-group-item-action d-flex justify-content-between align-items-center ' + active + '" style="cursor:pointer" onclick="_lsMetaSelectPage(\'' + _esc(p.id) + '\')">' +
                    '<div><strong>' + _esc(p.name) + '</strong><br><small class="opacity-75">ID: ' + _esc(p.id) + '</small></div>' +
                    (active ? '<span class="badge bg-primary">Selected</span>' : '') +
                '</div>';
            }).join('');

            body = '<p class="text-muted small">Logged in as <strong>' + _esc(w.user ? w.user.name : '') + '</strong>. Select the Facebook Page that runs your Lead Ads.</p>' +
                '<div class="d-flex gap-2 mb-3">' +
                    '<button class="btn btn-outline-danger btn-sm" onclick="_lsDisconnectExistingMetaSource()">Disconnect Existing Meta Connection</button>' +
                    '<button class="btn btn-outline-secondary btn-sm" onclick="_lsStartMetaWizard(true)">Start Over (Re-login)</button>' +
                '</div>' +
                '<div class="list-group mb-3">' + pageItems + '</div>' +
                '<div class="d-flex gap-2">' +
                    '<button class="btn btn-primary" onclick="_lsMetaStep3Next(event)" ' + (!w.selectedPage ? 'disabled' : '') + '>Next</button>' +
                '</div>';
        }

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
        }).join('') : '<p class="text-muted p-3">No lead forms found on this page. Make sure you have active Lead Ads.</p>';

        body = '<p class="text-muted small">Select lead forms to receive from <strong>' + _esc(w.selectedPage ? w.selectedPage.name : '') + '</strong>.</p>' +
            '<div class="list-group mb-3">' + formItems + '</div>' +
            (w.forms.length ? '<div class="mb-3"><button class="btn btn-sm btn-outline-secondary me-2" onclick="_lsMetaSelectAllForms()">Select All</button><button class="btn btn-sm btn-outline-secondary" onclick="_lsMetaClearForms()">Clear</button></div>' : '') +
            '<div class="d-flex gap-2">' +
                '<button class="btn btn-outline-secondary" onclick="_metaWizard.step=3; _lsRenderMetaWizard()">Back</button>' +
                '<button class="btn btn-primary" onclick="_metaWizard.step=5; _lsRenderMetaWizard()" ' + (!w.forms.length ? 'disabled' : '') + '>Next</button>' +
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
                <input class="form-control mb-2" id="mw-source-name" value="${_esc('Meta - ' + (w.selectedPage ? w.selectedPage.name : ''))}">
            </div>
        </div>
        <div class="d-flex gap-2 mt-3">
            <button class="btn btn-outline-secondary" onclick="_metaWizard.step=4; _lsRenderMetaWizard()">Back</button>
            <button class="btn btn-success" onclick="_lsMetaSave(event)">Save &amp; Activate</button>
        </div>`;
    }

    el.innerHTML = '<div class="card"><div class="card-header d-flex align-items-center gap-2"><strong>Connect Meta</strong><div class="ms-auto">' + stepNav + '</div></div><div class="card-body">' + body + '</div></div>';
}

async function _lsMetaStep1Next(evt) {
    var businessId = (document.getElementById('mw-business-id').value || '').trim();
    if (!businessId) { showToast('Please enter your Meta Business ID', 'danger'); return; }
    _metaWizard.businessId = businessId;
    _metaWizard.step = 2;
    _lsPersistMetaWizard();
    _lsRenderMetaWizard();
}

async function _lsMetaOpenFacebookLogin(evt) {
    var btn = _lsEventButton(evt);
    if (btn) { btn.disabled = true; btn.innerHTML = 'Loading...'; }
    var data;
    try {
        data = await _apiRequest('/lead-sources/meta/start-auth', {
            method: 'POST',
            headers: _apiJsonHeaders(_apiAuthHeaders()),
            body: JSON.stringify({ business_id: _metaWizard.businessId }),
            retries: 0,
            timeoutMs: 15000,
        });
    } catch (err) {
        if (btn) { btn.disabled = false; btn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="white" class="me-2"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>Login with Facebook'; }
        showToast((err && err.message) || 'Could not start OAuth', 'danger');
        return;
    }
    if (btn) { btn.disabled = false; btn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="white" class="me-2"><path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/></svg>Login with Facebook'; }
    window.location.href = data.auth_url;
}

function _lsMetaSelectPage(pageId) {
    _metaWizard.selectedPage = _metaWizard.pages.find(function(p) { return p.id === pageId; }) || null;
    _lsPersistMetaWizard();
    _lsRenderMetaWizard();
}

async function _lsDisconnectExistingMetaSource() {
    if (!confirm('Disconnect all existing Meta source connections for this tenant?')) return;
    var listRes = await authFetch('/api/lead-sources');
    if (!listRes.ok) {
        showToast(await _lsApiErrorMessage(listRes, 'Could not load sources'), 'danger');
        return;
    }
    var listData = await _lsReadJsonSafe(listRes);
    var metaSources = (listData.sources || []).filter(function(s) { return s.source_type === 'meta'; });
    if (!metaSources.length) {
        showToast('No Meta source found to disconnect', 'warning');
        return;
    }

    var disconnected = 0;
    var failed = [];
    for (var i = 0; i < metaSources.length; i++) {
        var s = metaSources[i];
        var res = await authFetch('/api/lead-sources/' + s.id + '/disconnect', { method: 'POST' });
        if (res.ok) {
            disconnected += 1;
        } else {
            failed.push({
                id: s.id,
                name: s.name,
                status: res.status,
                error: await _lsApiErrorMessage(res, 'Disconnect failed')
            });
        }
    }
    if (!disconnected) {
        var firstFail = failed[0] || {};
        showToast('Disconnect failed: ' + (firstFail.error || 'No source could be disconnected'), 'danger');
        return;
    }

    _lsClearPersistedMetaWizard();
    var cleanUrl = window.location.pathname;
    window.history.replaceState({}, '', cleanUrl + '?meta_tab=connect');
    _lsStartMetaWizard(true);
    if (failed.length) {
        showToast('Disconnected ' + disconnected + ' source(s). ' + failed.length + ' failed. Check Logs/Network for details.', 'warning');
    } else {
        showToast('Disconnected ' + disconnected + ' Meta source(s)', 'success');
    }
}

async function _lsMetaStep3Next(evt) {
    if (!_metaWizard.selectedPage) { showToast('Select a page first', 'danger'); return; }
    var btn = _lsEventButton(evt);
    if (btn) { btn.disabled = true; btn.textContent = 'Loading forms...'; }
    var data;
    try {
        data = await _apiRequest('/lead-sources/meta/page-forms', {
            method: 'POST',
            headers: _apiJsonHeaders(_apiAuthHeaders()),
            body: JSON.stringify({
                page_id: _metaWizard.selectedPage.id,
                page_access_token: _metaWizard.selectedPage.access_token,
                user_access_token: _metaWizard.longToken || ''
            }),
            retries: 0,
            timeoutMs: 15000,
        });
    } catch (err) {
        if (btn) { btn.disabled = false; btn.textContent = 'Next'; }
        var message = (err && err.message) || 'Could not load forms';
        if (String(message).indexOf('pages_manage_ads') !== -1) {
            message = 'Meta permission missing: pages_manage_ads. Click Start Over and login again to grant updated permissions.';
        }
        showToast(message, 'danger');
        return;
    }
    if (btn) { btn.disabled = false; btn.textContent = 'Next'; }
    _metaWizard.forms = data.forms || [];
    _metaWizard.selectedForms = _metaWizard.forms.slice();
    _metaWizard.step = 4;
    _lsPersistMetaWizard();
    _lsRenderMetaWizard();
}

function _lsMetaToggleForm(id, name, checked) {
    if (checked) {
        if (!_metaWizard.selectedForms.find(function(f) { return f.id === id; }))
            _metaWizard.selectedForms.push({ id: id, name: name });
    } else {
        _metaWizard.selectedForms = _metaWizard.selectedForms.filter(function(f) { return f.id !== id; });
    }
    _lsPersistMetaWizard();
}

function _lsMetaSelectAllForms() { _metaWizard.selectedForms = _metaWizard.forms.slice(); _lsPersistMetaWizard(); _lsRenderMetaWizard(); }
function _lsMetaClearForms()     { _metaWizard.selectedForms = []; _lsPersistMetaWizard(); _lsRenderMetaWizard(); }

async function _lsMetaSave(evt) {
    var name = ((document.getElementById('mw-source-name') || {}).value || '').trim()
               || ('Meta - ' + (_metaWizard.selectedPage ? _metaWizard.selectedPage.name : ''));
    var btn = _lsEventButton(evt);
    if (btn) { btn.disabled = true; btn.textContent = 'Saving...'; }
    var data;
    try {
        data = await _apiRequest('/lead-sources/meta/save-connection', {
            method: 'POST',
            headers: _apiJsonHeaders(_apiAuthHeaders()),
            body: JSON.stringify({
                name:              name,
                user_token:        _metaWizard.longToken,
                business_id:        _metaWizard.businessId,
                page_id:           _metaWizard.selectedPage.id,
                page_name:         _metaWizard.selectedPage.name,
                page_access_token: _metaWizard.selectedPage.access_token,
                selected_forms:    _metaWizard.selectedForms,
                verify_token:      'smk_' + _metaWizard.selectedPage.id,
            }),
            retries: 0,
            timeoutMs: 15000,
        });
    } catch (err) {
        if (btn) { btn.disabled = false; btn.textContent = 'Save & Activate'; }
        showToast((err && err.message) || 'Save failed', 'danger');
        return;
    }
    if (btn) { btn.disabled = false; btn.textContent = 'Save & Activate'; }
    _lsClearPersistedMetaWizard();
    showToast('Meta source connected!', 'success');
    await _lsLoadSources();
    _lsSwitchTab('sources');
}

// â”€â”€â”€ GOOGLE WIZARD â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function _lsStartGoogleWizard(forceFresh) {
    // Check if returning from OAuth callback
    var urlParams = new URLSearchParams(window.location.search);
    var sessionKey = urlParams.get('google_session');
    var persistedGoogleWizard = _lsLoadPersistedGoogleWizard();
    if (!forceFresh && sessionKey) {
        _googleWizard = {
            step: 2,
            sessionKey: sessionKey,
            user: null,
            accessToken: '',
            refreshToken: '',
            accessibleAccounts: [],
            discoveryError: '',
            oauthHealthy: false,
        };
        _lsPersistGoogleWizard();
        _lsRenderGoogleWizard();
        _lsGoogleLoadSession(sessionKey);
        return;
    }
    if (!forceFresh && persistedGoogleWizard && persistedGoogleWizard.step >= 2) {
        _googleWizard = Object.assign({
            step: 2,
            sessionKey: '',
            user: null,
            accessToken: '',
            refreshToken: '',
            accessibleAccounts: [],
            discoveryError: '',
            oauthHealthy: false,
        }, persistedGoogleWizard);
        _lsRenderGoogleWizard();
        return;
    }

    if (forceFresh) {
        _lsClearPersistedGoogleWizard();
        var cleanUrl = window.location.pathname;
        window.history.replaceState({}, '', cleanUrl + '?meta_tab=connect');
    }

    _googleWizard = {
        step: 1,
        sessionKey: '',
        user: null,
        accessToken: '',
        refreshToken: '',
        accessibleAccounts: [],
        discoveryError: '',
        oauthHealthy: false,
    };
    _lsPersistGoogleWizard();
    _lsRenderGoogleWizard();
}

function _lsGoogleManualAccounts() {
    var input = document.getElementById('gw-manual-customer-ids');
    if (!input) return [];
    var raw = String(input.value || '');
    var ids = raw.split(/[\n,\s;]+/).map(function(v) {
        return String(v || '').replace(/\D/g, '');
    }).filter(Boolean);
    var out = [];
    var seen = {};
    ids.forEach(function(cid) {
        if (seen[cid]) return;
        seen[cid] = true;
        out.push({
            customer_id: cid,
            customer_name: 'Google Ads ' + cid,
            resource_name: 'customers/' + cid,
        });
    });
    return out;
}

async function _lsGoogleLoadSession(sessionKey) {
    var el = document.getElementById('ls-wizard-area');
    var res;
    try {
        res = await authFetch('/api/lead-sources/google/auth-session/' + encodeURIComponent(sessionKey));
    } catch (err) {
        if (el) el.innerHTML = '<div class="alert alert-danger">' + _esc((err && err.message) || 'Could not restore Google session') + ' - <a href="#" onclick="event.preventDefault();_lsStartGoogleWizard()">Start over</a></div>';
        return;
    }
    if (!res.ok) {
        var errMsg = await _lsApiErrorMessage(res, 'Session expired');
        if (el) el.innerHTML = '<div class="alert alert-danger">' + _esc(errMsg) + ' - <a href="#" onclick="event.preventDefault();_lsStartGoogleWizard()">Start over</a></div>';
        return;
    }
    var data = await _lsReadJsonSafe(res);
    _googleWizard.user         = data.user;
    _googleWizard.accessToken  = data.access_token || '';
    _googleWizard.refreshToken = data.refresh_token || '';
    _googleWizard.accessibleAccounts = Array.isArray(data.accessible_accounts) ? data.accessible_accounts : [];
    _googleWizard.discoveryError = data.account_discovery_error || '';
    _googleWizard.oauthHealthy = !!data.oauth_healthy;
    _googleWizard.step         = 2;
    _lsPersistGoogleWizard();
    var cleanUrl = window.location.pathname;
    window.history.replaceState({}, '', cleanUrl);
    _lsRenderGoogleWizard();
}

function _lsRenderGoogleWizard() {
    var el = document.getElementById('ls-wizard-area');
    if (!el) return;
    var w = _googleWizard;

    var stepLabels = ['Login', 'Account Details', 'Save'];
    var stepNav = stepLabels.map(function(s, i) {
        var cls = (i + 1 === w.step) ? 'bg-danger' : (i + 1 < w.step) ? 'bg-success' : 'bg-secondary';
        return '<span class="badge ' + cls + ' me-1">' + (i + 1 < w.step ? 'Done' : (i + 1)) + '. ' + s + '</span>';
    }).join('');

    var body = '';

    if (w.step === 1) {
        body = `
        <p class="text-muted small">Click the button below to log in with the Google account that manages your Google Ads account.</p>
        <div class="d-grid gap-2 mb-3" style="max-width:300px">
            <button class="btn btn-outline-danger btn-lg d-flex align-items-center justify-content-center gap-2" onclick="_lsGoogleOpenLogin(event)">
                <svg width="20" height="20" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
                Login with Google
            </button>
        </div>
        <p class="text-muted small">You'll be redirected to Google to authorize access to your Google Ads Lead Forms.</p>`;

    } else if (w.step === 2) {
        var accounts = Array.isArray(w.accessibleAccounts) ? w.accessibleAccounts : [];
        var accountRows = accounts.map(function(acc, idx) {
            var cid = _esc(acc.customer_id || '');
            var cname = _esc(acc.customer_name || ('Google Ads ' + cid));
            return '<label class="list-group-item d-flex align-items-center gap-2">' +
                '<input class="form-check-input me-2" type="checkbox" value="' + cid + '" data-name="' + cname + '" data-resource="' + _esc(acc.resource_name || ('customers/' + cid)) + '" ' + (idx === 0 ? 'checked' : '') + '>' +
                '<span><strong>' + cname + '</strong><br><small class="text-muted">Customer ID: ' + cid + '</small></span>' +
            '</label>';
        }).join('');

        var oauthBadge = w.oauthHealthy
            ? '<span class="badge bg-success">OAuth Healthy</span>'
            : '<span class="badge bg-warning text-dark">OAuth Needs Attention</span>';

        body = `
        <p class="text-muted small">Connected as <strong>${_esc(w.user ? (w.user.name || w.user.email) : '')}</strong>.</p>
        <div class="mb-2">${oauthBadge}</div>
        ${w.discoveryError ? '<div class="alert alert-warning py-2 small">Account discovery warning: ' + _esc(w.discoveryError) + '</div>' : ''}
        <div class="mb-3">
            <label class="form-label">Google Ads Accounts <span class="text-danger">*</span></label>
            ${accounts.length
                ? '<div id="gw-account-list" class="list-group" style="max-height:220px; overflow:auto">' + accountRows + '</div>'
                : '<div class="alert alert-danger py-2 small mb-0">No accessible Google Ads accounts found. Ensure GOOGLE_DEVELOPER_TOKEN is configured and this Google user has Ads account access.</div>'
            }
        </div>
        ${accounts.length ? '' : `
        <div class="mb-3">
            <label class="form-label">Manual Customer IDs (fallback)</label>
            <textarea id="gw-manual-customer-ids" class="form-control" rows="3" placeholder="Paste one or more Google Ads Customer IDs, comma/newline separated. Example: 1234567890, 9988776655"></textarea>
            <div class="form-text">Use this if account discovery fails but access is shared to this Google login.</div>
        </div>
        `}
        <div class="mb-3">
            <label class="form-label">Source Name</label>
            <input class="form-control" id="gw-source-name" value="${_esc('Google - ' + (w.user ? (w.user.email || '') : ''))}">
        </div>
        <div class="d-flex gap-2">
            <button class="btn btn-outline-secondary" onclick="_lsStartGoogleWizard(true)">Start Over</button>
            <button class="btn btn-success" onclick="_lsGoogleSave(event)">Save &amp; Activate</button>
        </div>`;
    }

    el.innerHTML = '<div class="card"><div class="card-header d-flex align-items-center gap-2"><strong>Connect Google</strong><div class="ms-auto">' + stepNav + '</div></div><div class="card-body">' + body + '</div></div>';
}

async function _lsGoogleOpenLogin(evt) {
    var btn = _lsEventButton(evt);
    if (btn) { btn.disabled = true; btn.innerHTML = 'Loading...'; }
    var res;
    try {
        res = await authFetch('/api/lead-sources/google/start-auth', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    } catch (err) {
        if (btn) { btn.disabled = false; btn.innerHTML = 'Login with Google'; }
        showToast((err && err.message) || 'Could not start OAuth', 'danger');
        return;
    }
    var data = await _lsReadJsonSafe(res);
    if (btn) { btn.disabled = false; btn.innerHTML = 'Login with Google'; }
    if (!res.ok) { showToast((data && data.error) || 'Could not start OAuth', 'danger'); return; }
    window.location.href = data.auth_url;
}

async function _lsGoogleSave(evt) {
    var name       = ((document.getElementById('gw-source-name') || {}).value || '').trim();
    var selectedAccounts = [];
    var listRoot = document.getElementById('gw-account-list');
    if (listRoot) {
        listRoot.querySelectorAll('input[type="checkbox"]:checked').forEach(function(cb) {
            var cid = (cb.value || '').trim();
            if (!cid) return;
            selectedAccounts.push({
                customer_id: cid,
                customer_name: (cb.getAttribute('data-name') || '').trim(),
                resource_name: (cb.getAttribute('data-resource') || '').trim(),
            });
        });
    }
    if (!selectedAccounts.length) {
        selectedAccounts = _lsGoogleManualAccounts();
    }
    if (!selectedAccounts.length) {
        showToast('Select at least one Google Ads account or provide manual Customer IDs', 'danger');
        return;
    }
    var btn = _lsEventButton(evt);
    if (btn) { btn.disabled = true; btn.textContent = 'Saving...'; }
    var res;
    try {
        res = await authFetch('/api/lead-sources/google/save-connection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name:          name || ('Google - ' + (_googleWizard.user ? _googleWizard.user.email : '')),
                client_id:     '__platform__',
                client_secret: '__platform__',
                refresh_token: _googleWizard.refreshToken,
                user_email:    _googleWizard.user ? _googleWizard.user.email : '',
                selected_accounts: selectedAccounts,
            }),
        });
    } catch (err) {
        if (btn) { btn.disabled = false; btn.textContent = 'Save & Activate'; }
        showToast((err && err.message) || 'Save failed', 'danger');
        return;
    }
    if (btn) { btn.disabled = false; btn.textContent = 'Save & Activate'; }
    var data = await _lsReadJsonSafe(res);
    if (!res.ok) { showToast(data.error || 'Save failed', 'danger'); return; }
    _lsClearPersistedGoogleWizard();
    showToast('Google source connected!', 'success');
    await _lsLoadSources();
    _lsSwitchTab('sources');
}
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// TAB: Manual / Webhook - Add / Edit form
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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

    var connectedFormsPanel = isEdit ? _lsRenderConnectedFormsPanel(source) : '';

    el.innerHTML = `
    <h5>${isEdit ? 'Source Details' : 'Add Source (Manual / Webhook)'}</h5>
    ${connectedFormsPanel}
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
        <h6>Field Mapping <small class="text-muted fw-normal">(JSON: source field -> LMS field)</small></h6>
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
    if (!confirm('Remove this source from the active list? Existing leads and logs will remain unchanged.')) return;
    var res = await authFetch('/api/lead-sources/' + id + '/remove', { method: 'POST' });
    if (!res.ok && (res.status === 404 || res.status === 405)) {
        res = await authFetch('/api/lead-sources/' + id, { method: 'DELETE' });
    }
    if (!res.ok) { showToast(await _lsApiErrorMessage(res, 'Remove failed'), 'danger'); return; }
    showToast('Source removed from active list', 'success');
    _lsEditId = null;
    if (_lsTab === 'archived') {
        await _lsLoadArchivedSources();
    } else {
        await _lsLoadSources();
        _lsSwitchTab('sources');
    }
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// TAB: Test Lead
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

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
            <button class="btn btn-primary w-100" onclick="_lsRunTestLead(event)">Run Test Lead</button>
        </div>
        <div class="col-md-7" id="ls-test-result">
            <div class="text-muted small pt-5 text-center">Results will appear here after you run a test lead.</div>
        </div>
    </div>`;
}

async function _lsRunTestLead(evt) {
    var sourceId = (document.getElementById('ls-test-source-id') || {}).value;
    if (!sourceId) { showToast('Select a source', 'danger'); return; }
    var btn = _lsEventButton(evt);
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

    var res;
    try {
        res = await authFetch('/api/lead-sources/' + sourceId + '/inject-test-lead', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
    } catch (err) {
        if (btn) { btn.disabled = false; btn.textContent = 'Run Test Lead'; }
        var netEl = document.getElementById('ls-test-result');
        if (netEl) netEl.innerHTML = '<div class="alert alert-danger">' + _esc((err && err.message) || 'Network error while running test lead') + '</div>';
        return;
    }
    if (btn) { btn.disabled = false; btn.textContent = 'Run Test Lead'; }

    var data = await _lsReadJsonSafe(res);
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
    var statusIcon  = r.status === 'created' ? 'OK' : r.status === 'error' ? 'FAIL' : 'WARN';

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
            '<tr><th>Campaign</th><td>' + _esc(log.campaign_name || '-') + '</td></tr>' +
        '</table>' : '');
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// TAB: Validate â€” PASS/FAIL report
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function _lsRenderValidate() {
    var el = document.getElementById('ls-body');
    var metaSources   = _lsSources.filter(function(s) { return s.source_type === 'meta'; });
    var googleSources = _lsSources.filter(function(s) { return s.source_type === 'google'; });

    var metaOpts = [{ id: '', name: '-- None --' }].concat(metaSources).map(function(s) {
        return '<option value="' + _esc(String(s.id)) + '">' + _esc(s.name || '-- None --') + '</option>';
    }).join('');
    var googleOpts = [{ id: '', name: '-- None --' }].concat(googleSources).map(function(s) {
        return '<option value="' + _esc(String(s.id)) + '">' + _esc(s.name || '-- None --') + '</option>';
    }).join('');

    el.innerHTML = `
    <div class="row g-4">
        <div class="col-md-4">
            <h5>Phase META-1.1 Validation</h5>
            <p class="text-muted small">Runs all 7 checks and generates a PASS/FAIL deployment report.</p>
            <div class="mb-3">
                <label class="form-label">Meta Source</label>
                <select class="form-select" id="ls-val-meta">${metaOpts}</select>
            </div>
            <div class="mb-3">
                <label class="form-label">Google Source</label>
                <select class="form-select" id="ls-val-google">${googleOpts}</select>
            </div>
            <button class="btn btn-dark w-100" onclick="_lsRunValidation(event)">Run Validation</button>
            <p class="text-muted small mt-2">Test leads will be created in your database.</p>

            <hr>
            <h6 class="mb-2">Google Foundation Status</h6>
            <p class="text-muted small mb-2">Checks attribution capture + account connection health.</p>
            <button class="btn btn-outline-primary w-100" onclick="_lsRunFoundationValidation(event)">Check Foundation</button>
        </div>
        <div class="col-md-8">
            <div id="ls-foundation-result" class="mb-3"></div>
            <div id="ls-val-result">
                <div class="text-muted small pt-4 text-center">Select sources and click Run Validation.</div>
            </div>
        </div>
    </div>`;

    _lsRenderFoundationStatus(null, 'Click "Check Foundation" to validate GCLID/UTM capture and Google OAuth/account setup.');
}

async function _lsRunValidation(evt) {
    var metaId   = (document.getElementById('ls-val-meta') || {}).value;
    var googleId = (document.getElementById('ls-val-google') || {}).value;
    var btn = _lsEventButton(evt);
    if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Running...'; }

    var el = document.getElementById('ls-val-result');
    el.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary mb-3"></div><p class="text-muted">Running 7 validation checks...</p></div>';

    var res;
    try {
        res = await authFetch('/api/lead-sources/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                meta_source_id:   metaId   ? parseInt(metaId)   : null,
                google_source_id: googleId ? parseInt(googleId) : null,
            }),
        });
    } catch (err) {
        if (btn) { btn.disabled = false; btn.textContent = 'Run Validation'; }
        el.innerHTML = '<div class="alert alert-danger">' + _esc((err && err.message) || 'Validation request failed') + '</div>';
        return;
    }
    if (btn) { btn.disabled = false; btn.textContent = 'Run Validation'; }

    var data = await _lsReadJsonSafe(res);
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
            '<span class="fs-2 me-3">' + (ready ? 'READY' : 'ATTN') + '</span>' +
            '<div><strong>' + _esc(data.summary || (passCount + '/7 checks passed')) + '</strong><br>' +
            '<span class="fs-5">Deployment Ready: <strong>' + (ready ? 'YES' : 'NO') + '</strong></span></div>' +
        '</div>' +
        '<table class="table table-bordered align-middle">' +
            '<thead class="table-light"><tr><th>Check</th><th style="width:90px">Result</th><th>Details</th></tr></thead>' +
            '<tbody>' + rows + '</tbody>' +
        '</table>' +
        '<p class="text-muted small">Validation run at: ' + _esc(data.run_at || '') + '</p>';
}

function _lsSubBadge(label, passed) {
    return '<span class="badge bg-' + (passed ? 'success' : 'danger') + ' text-wrap">' + _esc(label) + ' ' + (passed ? '[OK]' : '[X]') + '</span>';
}

function _lsRenderFoundationStatus(status, hint) {
    var el = document.getElementById('ls-foundation-result');
    if (!el) return;

    if (!status) {
        el.innerHTML = '<div class="alert alert-light border mb-0"><small class="text-muted">' + _esc(hint || 'No data yet') + '</small></div>';
        return;
    }

    function row(label, ok, detail) {
        return '<tr>' +
            '<td>' + _esc(label) + '</td>' +
            '<td><span class="badge bg-' + (ok ? 'success' : 'danger') + '">' + (ok ? 'YES' : 'NO') + '</span></td>' +
            '<td><small class="text-muted">' + _esc(detail || '') + '</small></td>' +
        '</tr>';
    }

    var accounts = status.connected_accounts || [];
    var accountText = accounts.length ? accounts.map(function(a) { return a.customer_id; }).join(', ') : 'No accounts selected';
    var oauthDetail = (status.oauth_test && status.oauth_test.message) || '';

    el.innerHTML =
        '<div class="card border-primary-subtle">' +
            '<div class="card-header bg-light"><strong>Google Foundation Validation</strong></div>' +
            '<div class="card-body p-0">' +
                '<table class="table table-sm mb-0">' +
                    '<thead class="table-light"><tr><th>Check</th><th style="width:90px">Status</th><th>Details</th></tr></thead>' +
                    '<tbody>' +
                        row('GCLID detected', !!status.gclid_detected, status.gclid_detected ? 'Detected in tracking snapshot or ingestion logs' : 'Not detected yet') +
                        row('UTM detected', !!status.utm_detected, status.utm_detected ? 'UTM parameters available' : 'No UTM values found yet') +
                        row('Account connected', !!status.account_connected, accountText) +
                        row('OAuth healthy', !!status.oauth_healthy, oauthDetail) +
                    '</tbody>' +
                '</table>' +
            '</div>' +
        '</div>';
}

async function _lsRunFoundationValidation(evt) {
    var btn = _lsEventButton(evt);
    var googleId = (document.getElementById('ls-val-google') || {}).value;
    if (!googleId) {
        showToast('Select a Google source first', 'danger');
        return;
    }
    if (btn) { btn.disabled = true; btn.textContent = 'Checking...'; }

    var tracker = window.smAttributionTracker;
    var snapshot = tracker && typeof tracker.captureFromLocation === 'function'
        ? tracker.captureFromLocation()
        : {};

    var res;
    try {
        res = await authFetch('/api/lead-sources/google/foundation-status?source_id=' + encodeURIComponent(String(googleId)));
    } catch (err) {
        if (btn) { btn.disabled = false; btn.textContent = 'Check Foundation'; }
        _lsRenderFoundationStatus(null, (err && err.message) || 'Failed to load foundation status');
        return;
    }
    if (btn) { btn.disabled = false; btn.textContent = 'Check Foundation'; }

    var data = await _lsReadJsonSafe(res);
    if (!res.ok) {
        _lsRenderFoundationStatus(null, data.error || 'Foundation check failed');
        return;
    }

    var snapshotGclid = !!(snapshot && snapshot.gclid);
    var snapshotUtm = !!(snapshot && (snapshot.utm_source || snapshot.utm_medium || snapshot.utm_campaign || snapshot.utm_content || snapshot.utm_term));
    data.gclid_detected = !!data.gclid_detected || snapshotGclid;
    data.utm_detected = !!data.utm_detected || snapshotUtm;

    _lsRenderFoundationStatus(data, '');
}

async function _lsRenderTierTest() {
    var el = document.getElementById('ls-body');
    if (!el) return;

    el.innerHTML =
        '<div class="row g-4">' +
            '<div class="col-lg-5">' +
                '<div class="card"><div class="card-body">' +
                    '<h5 class="card-title mb-3">Meta Marketing API Tier Test</h5>' +
                    '<div class="mb-2"><label class="form-label">Access Token</label><textarea id="ls-tier-token" class="form-control" rows="3" placeholder="Meta user access token"></textarea></div>' +
                    '<div class="mb-2"><label class="form-label">Ad Account ID</label><input id="ls-tier-ad-account" class="form-control" placeholder="e.g. 1234567890 or act_1234567890"></div>' +
                    '<div class="mb-2"><label class="form-label">Page ID</label><input id="ls-tier-page-id" class="form-control" placeholder="e.g. 112233445566"></div>' +
                    '<div class="row g-2">' +
                        '<div class="col-6"><label class="form-label">Target Success Calls</label><input id="ls-tier-target" type="number" class="form-control" value="500"></div>' +
                        '<div class="col-6"><label class="form-label">Batch Size</label><input id="ls-tier-batch" type="number" class="form-control" value="15"></div>' +
                        '<div class="col-6"><label class="form-label">Min Delay (ms)</label><input id="ls-tier-min-delay" type="number" class="form-control" value="350"></div>' +
                        '<div class="col-6"><label class="form-label">Max Delay (ms)</label><input id="ls-tier-max-delay" type="number" class="form-control" value="900"></div>' +
                    '</div>' +
                    '<div class="d-flex gap-2 mt-3 flex-wrap">' +
                        '<button class="btn btn-primary btn-sm" onclick="_lsTierStartRun()">Start Run</button>' +
                        '<button class="btn btn-outline-primary btn-sm" onclick="_lsTierRunBatch()">Run Batch</button>' +
                        '<button class="btn btn-outline-success btn-sm" onclick="_lsTierAutoRun()">Auto Run</button>' +
                        '<button class="btn btn-outline-danger btn-sm" onclick="_lsTierStopRun()">Stop</button>' +
                    '</div>' +
                    '<p class="text-muted small mt-3 mb-0">Rate-limit safe mode: each call is delayed and retries back off on rate-limit responses.</p>' +
                '</div></div>' +
            '</div>' +
            '<div class="col-lg-7">' +
                '<div class="card"><div class="card-body">' +
                    '<div class="d-flex justify-content-between align-items-center mb-3">' +
                        '<h5 class="card-title mb-0">Dashboard</h5>' +
                        '<button class="btn btn-sm btn-outline-secondary" onclick="_lsTierRefreshDashboard()">Refresh</button>' +
                    '</div>' +
                    '<div id="ls-tier-dashboard" class="text-muted">Loading dashboard...</div>' +
                '</div></div>' +
            '</div>' +
        '</div>';

    await _lsTierRefreshDashboard();
}

function _lsTierReadConfig() {
    return {
        ad_account_id: (document.getElementById('ls-tier-ad-account') || {}).value || '',
        page_id: (document.getElementById('ls-tier-page-id') || {}).value || '',
        target_success_calls: parseInt(((document.getElementById('ls-tier-target') || {}).value || '500'), 10),
        batch_size: parseInt(((document.getElementById('ls-tier-batch') || {}).value || '15'), 10),
        min_delay_ms: parseInt(((document.getElementById('ls-tier-min-delay') || {}).value || '350'), 10),
        max_delay_ms: parseInt(((document.getElementById('ls-tier-max-delay') || {}).value || '900'), 10),
    };
}

function _lsTierReadToken() {
    return ((document.getElementById('ls-tier-token') || {}).value || '').trim();
}

function _lsTierRenderDashboardPayload(payload) {
    var el = document.getElementById('ls-tier-dashboard');
    if (!el) return;

    var run = payload && payload.run ? payload.run : null;
    var agg = payload && payload.aggregate ? payload.aggregate : null;
    var dash = run && run.dashboard ? run.dashboard : null;
    if (!dash && agg) {
        dash = {
            total_marketing_api_calls: agg.total_marketing_api_calls || 0,
            success_percent: agg.success_percent || 0,
            calls_counted_toward_meta_testing: agg.calls_counted_toward_meta_testing || 0,
            target_success_calls: 500,
            remaining_success_calls_to_target: Math.max(0, 500 - (agg.calls_counted_toward_meta_testing || 0)),
            goal_met: (agg.calls_counted_toward_meta_testing || 0) >= 500,
        };
    }

    if (!dash) {
        el.innerHTML = '<div class="text-muted">No run data yet.</div>';
        return;
    }

    el.innerHTML =
        '<div class="row g-2 mb-3">' +
            '<div class="col-md-4"><div class="border rounded p-2"><div class="small text-muted">Total Marketing API Calls</div><div class="fs-4 fw-semibold">' + (dash.total_marketing_api_calls || 0) + '</div></div></div>' +
            '<div class="col-md-4"><div class="border rounded p-2"><div class="small text-muted">Success %</div><div class="fs-4 fw-semibold">' + (dash.success_percent || 0) + '%</div></div></div>' +
            '<div class="col-md-4"><div class="border rounded p-2"><div class="small text-muted">Calls Counted</div><div class="fs-4 fw-semibold">' + (dash.calls_counted_toward_meta_testing || 0) + '</div></div></div>' +
        '</div>' +
        '<div class="mb-2">Goal: <strong>' + (dash.target_success_calls || 500) + '</strong> successful calls | Remaining: <strong>' + (dash.remaining_success_calls_to_target || 0) + '</strong></div>' +
        '<div>Status: <span class="badge bg-' + (dash.goal_met ? 'success' : 'secondary') + '">' + (dash.goal_met ? 'Goal Met' : 'In Progress') + '</span>' +
        (run ? ' <span class="ms-2 text-muted small">Run #' + run.id + ' (' + _esc(run.status || '') + ')</span>' : '') + '</div>';
}

async function _lsTierStartRun() {
    try {
        var config = _lsTierReadConfig();
        var runRes = await _apiRequest('/lead-sources/meta/tier-tests/start', {
            method: 'POST',
            headers: _apiAuthHeaders(),
            body: JSON.stringify(config),
        });
        _lsTierRunId = runRes && runRes.run ? runRes.run.id : null;
        _lsTierRenderDashboardPayload({ run: runRes.run });
        showToast('Tier test run started', 'success');
    } catch (err) {
        showToast((err && err.message) || 'Failed to start run', 'error');
    }
}

async function _lsTierRunBatch() {
    if (!_lsTierRunId) {
        showToast('Start a run first', 'error');
        return;
    }
    var token = _lsTierReadToken();
    if (!token) {
        showToast('Access token is required', 'error');
        return;
    }
    try {
        var res = await _apiRequest('/lead-sources/meta/tier-tests/' + _lsTierRunId + '/batch', {
            method: 'POST',
            headers: _apiAuthHeaders(),
            body: JSON.stringify({ access_token: token }),
            timeoutMs: 90000,
        });
        _lsTierRenderDashboardPayload({ run: res.run });
    } catch (err) {
        showToast((err && err.message) || 'Batch run failed', 'error');
    }
}

async function _lsTierAutoRun() {
    if (_lsTierAutoRunning) return;
    if (!_lsTierRunId) {
        showToast('Start a run first', 'error');
        return;
    }
    var token = _lsTierReadToken();
    if (!token) {
        showToast('Access token is required', 'error');
        return;
    }

    _lsTierAutoRunning = true;
    try {
        for (var i = 0; i < 1000; i++) {
            if (!_lsTierAutoRunning) break;
            var res = await _apiRequest('/lead-sources/meta/tier-tests/' + _lsTierRunId + '/batch', {
                method: 'POST',
                headers: _apiAuthHeaders(),
                body: JSON.stringify({ access_token: token }),
                timeoutMs: 90000,
            });
            _lsTierRenderDashboardPayload({ run: res.run });
            if (res && res.run && res.run.dashboard && res.run.dashboard.goal_met) break;
        }
    } catch (err) {
        showToast((err && err.message) || 'Auto run failed', 'error');
    } finally {
        _lsTierAutoRunning = false;
    }
}

async function _lsTierStopRun() {
    _lsTierAutoRunning = false;
    if (!_lsTierRunId) return;
    try {
        var res = await _apiRequest('/lead-sources/meta/tier-tests/' + _lsTierRunId + '/stop', {
            method: 'POST',
            headers: _apiAuthHeaders(),
        });
        _lsTierRenderDashboardPayload({ run: res.run });
    } catch (_err) {}
}

async function _lsTierRefreshDashboard() {
    try {
        var data = await _apiRequest('/lead-sources/meta/tier-tests/dashboard', {
            headers: _apiAuthHeaders(),
        });
        var run = null;
        if (_lsTierRunId && data && data.runs) {
            run = data.runs.find(function(r) { return r.id === _lsTierRunId; }) || null;
        }
        if (!run && data && data.runs && data.runs.length) run = data.runs[0];
        if (run) _lsTierRunId = run.id;
        _lsTierRenderDashboardPayload({ run: run, aggregate: data.aggregate || {} });
    } catch (err) {
        var el = document.getElementById('ls-tier-dashboard');
        if (el) el.innerHTML = '<div class="text-danger">' + _esc((err && err.message) || 'Failed to load dashboard') + '</div>';
    }
}

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// TAB: Logs
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

async function _lsLoadLogs(page) {
    if (!page) page = 1;
    _lsLogPage = page;
    var el = document.getElementById('ls-body');
    el.innerHTML = '<div class="text-center py-5 text-muted">Loading logs...</div>';

    var res;
    try {
        res = await authFetch('/api/lead-sources/logs?page=' + page + '&per_page=' + _lsLogPerPage);
    } catch (err) {
        el.innerHTML = '<p class="text-danger">' + _esc((err && err.message) || 'Failed to load logs.') + '</p>';
        return;
    }
    if (!res.ok) { el.innerHTML = '<p class="text-danger">' + _esc(await _lsApiErrorMessage(res, 'Failed to load logs.')) + '</p>'; return; }
    var data = await _lsReadJsonSafe(res);
    _lsLogTotal = data.total || 0;

    function statusBadge(s) {
        var map = { processed: 'success', duplicate: 'warning text-dark', error: 'danger', queued: 'secondary' };
        var cls = map[s] || 'secondary';
        return '<span class="badge bg-' + cls + '">' + _esc(s) + '</span>';
    }

    var rows = (data.logs || []).map(function(l) {
        return '<tr>' +
            '<td>' + (_lsDateFromIso(l.received_at) ? _lsDateFromIso(l.received_at).toLocaleString() : '-') + '</td>' +
            '<td>' + (SOURCE_TYPE_LABELS[l.source_type] || l.source_type) + '</td>' +
            '<td>' + _esc(l.campaign_name || '-') + '</td>' +
            '<td>' + statusBadge(l.status) + '</td>' +
            '<td>' + (l.lead_id ? '#' + l.lead_id : '-') + '</td>' +
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

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// TAB: Reports
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

async function _lsLoadReports() {
    var el = document.getElementById('ls-body');
    el.innerHTML = '<div class="text-center py-5 text-muted">Loading reports...</div>';

    var results;
    try {
        results = await Promise.all([
            authFetch('/api/lead-sources/reports/by-source'),
            authFetch('/api/lead-sources/reports/by-campaign'),
        ]);
    } catch (err) {
        el.innerHTML = '<p class="text-danger">' + _esc((err && err.message) || 'Failed to load reports.') + '</p>';
        return;
    }
    if (!results[0].ok && !results[1].ok) {
        el.innerHTML = '<p class="text-danger">Could not load reports right now.</p>';
        return;
    }
    var bySource   = results[0].ok   ? ((await _lsReadJsonSafe(results[0])).rows || []) : [];
    var byCampaign = results[1].ok   ? ((await _lsReadJsonSafe(results[1])).rows || []) : [];

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

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// Utilities
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

function _esc(s) {
    if (s === null || s === undefined) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function _lsDateFromIso(iso) {
    if (!iso) return null;
    var text = String(iso).trim();
    if (!text) return null;
    // Backend stores UTC datetimes without timezone; treat naive timestamps as UTC.
    if (!/(Z|[+-]\d\d:\d\d)$/i.test(text)) text += 'Z';
    var d = new Date(text);
    return isNaN(d.getTime()) ? null : d;
}

function _lsRelTime(iso) {
    if (!iso) return '-';
    var d = _lsDateFromIso(iso);
    if (!d) return '-';
    var diff = Math.floor((Date.now() - d.getTime()) / 1000);
    if (diff < 0) diff = 0;
    if (diff < 60)    return diff + 's ago';
    if (diff < 3600)  return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return d.toLocaleDateString();
}
