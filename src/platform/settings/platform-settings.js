// Platform Settings — stub view.

function renderPlatformSettings() {
  const el = document.getElementById('platContent');
  if (!el) return;

  el.innerHTML = `
    <div class="plat-tabs">
      <button class="plat-tab active">General</button>
      <button class="plat-tab">Security</button>
      <button class="plat-tab">Notifications</button>
      <button class="plat-tab">API Keys</button>
      <button class="plat-tab">Billing</button>
    </div>

    <div class="plat-card">
      <h4 style="margin:0 0 18px;font-size:15px;color:#0f172a;">Platform Information</h4>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
        ${[
          ['Platform Name',    'SocioMonkey Platform',        'text'],
          ['Domain',           'sociomonkey.ai',              'text'],
          ['Contact Email',    'aseem@sociomonkey.com',       'email'],
          ['Support Email',    'support@sociomonkey.ai',      'email'],
          ['Timezone',         'Asia/Kolkata (IST)',          'text'],
          ['Date Format',      'DD/MM/YYYY',                  'text'],
        ].map(([label, value, type]) => `
          <div>
            <label style="font-size:12px;font-weight:600;color:#374151;display:block;margin-bottom:5px;">${label}</label>
            <input type="${type}" value="${value}"
                   style="width:100%;padding:9px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;outline:none;box-sizing:border-box;color:#0f172a;">
          </div>`).join('')}
      </div>
      <div style="margin-top:20px;">
        <button class="plat-btn plat-btn-primary">Save Changes</button>
        <button class="plat-btn plat-btn-outline" style="margin-left:10px;">Cancel</button>
      </div>
    </div>

    <div class="plat-card">
      <h4 style="margin:0 0 18px;font-size:15px;color:#0f172a;">Danger Zone</h4>
      <div style="display:flex;align-items:center;justify-content:space-between;padding:14px;border:1px solid #fee2e2;border-radius:10px;background:#fff5f5;">
        <div>
          <div style="font-weight:600;color:#dc2626;font-size:14px;">Reset Platform Data</div>
          <div style="font-size:12px;color:#64748b;margin-top:3px;">Permanently remove all platform configuration and cached data.</div>
        </div>
        <button class="plat-btn plat-btn-danger">Reset</button>
      </div>
    </div>
  `;
}

function renderPlatformBilling() {
  const el = document.getElementById('platContent');
  if (!el) return;

  el.innerHTML = `
    <div class="plat-empty" style="margin-top:60px;">
      <div class="plat-empty-icon">💳</div>
      <div class="plat-empty-title">Billing & Subscriptions</div>
      <div class="plat-empty-desc">Subscription management, invoices, and revenue tracking coming soon.</div>
    </div>
  `;
}
