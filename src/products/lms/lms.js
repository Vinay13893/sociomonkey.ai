// ============================================================================
// LMS (Lead Management System) — Ganga Realty product module
//
// The LMS product mirrors the CRM product for Ganga Realty.
// All lead management, project tracking, pipeline, and reports are shared
// with the CRM module — this file provides LMS-specific overrides and the
// LMS home page rendered when activeTab === 'product_home' for this product.
// ============================================================================

/**
 * Render the LMS product home / landing page.
 * Called by showContent() when activeTab === 'product_home' and currentProduct === 'lms'.
 */
function renderLmsHome() {
  const content = document.getElementById('content')
  if (!content) return

  const tenantName = (tenantConfig && (tenantConfig.brand_name || tenantConfig.name)) || 'Ganga Realty'

  content.innerHTML = `
    <div style="padding:32px;max-width:860px;margin:0 auto;">
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:28px;">
        <div style="width:56px;height:56px;border-radius:14px;background:linear-gradient(135deg,#1e3a5f,#3b82f6);
             display:flex;align-items:center;justify-content:center;font-size:26px;box-shadow:0 4px 12px rgba(30,58,95,.3);">
          📋
        </div>
        <div>
          <h1 style="margin:0;font-size:22px;font-weight:800;color:#0f172a;">${tenantName} — Lead Management System</h1>
          <p style="margin:4px 0 0;color:#64748b;font-size:14px;">
            Track, nurture and convert your leads from a single hub.
          </p>
        </div>
      </div>

      <!-- Quick-action cards -->
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:14px;margin-bottom:32px;">
        ${[
          { key:'dashboard', icon:'📊', title:'Dashboard',    desc:'Live KPIs & funnel snapshot' },
          { key:'leads',     icon:'👥', title:'Leads',        desc:'Browse & manage all leads'   },
          { key:'projects',  icon:'🏢', title:'Projects',     desc:'Real-estate project catalog'  },
          { key:'pipeline',  icon:'📈', title:'Pipeline',     desc:'Drag-and-drop Kanban board'  },
          { key:'reports',   icon:'📊', title:'Reports',      desc:'Performance analytics'        },
        ].map(c => `
          <div onclick="activeTab='${c.key}';renderApp()"
               style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px 16px;
                      cursor:pointer;transition:all .15s;box-shadow:0 1px 4px rgba(2,6,23,.06);"
               onmouseover="this.style.boxShadow='0 4px 16px rgba(30,58,95,.15)';this.style.borderColor='#93c5fd'"
               onmouseout="this.style.boxShadow='0 1px 4px rgba(2,6,23,.06)';this.style.borderColor='#e2e8f0'">
            <div style="font-size:28px;margin-bottom:10px;">${c.icon}</div>
            <div style="font-size:14px;font-weight:700;color:#0f172a;margin-bottom:4px;">${c.title}</div>
            <div style="font-size:12px;color:#64748b;">${c.desc}</div>
          </div>
        `).join('')}
      </div>

      <!-- Info banner -->
      <div style="background:linear-gradient(135deg,#eff6ff,#dbeafe);border:1px solid #bfdbfe;
           border-radius:12px;padding:18px 20px;display:flex;align-items:flex-start;gap:14px;">
        <div style="font-size:22px;flex-shrink:0;margin-top:2px;">ℹ️</div>
        <div>
          <div style="font-size:14px;font-weight:700;color:#1e40af;margin-bottom:4px;">
            Lead Management System — Connected
          </div>
          <div style="font-size:13px;color:#1d4ed8;line-height:1.6;">
            Your Ganga Realty LMS is now integrated with the SocioMonkey platform.
            All lead, project and pipeline data is stored centrally and accessible
            from the tabs above.  Use the left sidebar to navigate between modules.
          </div>
        </div>
      </div>
    </div>
  `
}
