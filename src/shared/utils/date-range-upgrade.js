(function () {
  if (window.__SM_DATE_RANGE_UPGRADE_INSTALLED__) return
  window.__SM_DATE_RANGE_UPGRADE_INSTALLED__ = true

  var PRESETS = [
    ['today', 'Today'],
    ['yesterday', 'Yesterday'],
    ['this-week', 'This week'],
    ['last-7-days', 'Last 7 days'],
    ['last-week', 'Last week'],
    ['last-14-days', 'Last 14 days'],
    ['this-month', 'This month'],
    ['last-30-days', 'Last 30 days'],
    ['last-month', 'Last month'],
    ['all-time', 'All time'],
  ]

  var LEGACY_PRESET_MAP = {
    today: 'today',
    this_week: 'this-week',
    this_month: 'this-month',
    last_30_days: 'last-30-days',
    last_month: 'last-month',
    custom: 'custom',
    '': 'all-time',
  }

  var CONFIGS = [
    { fromId: 'dashDateFrom', toId: 'dashDateTo', label: 'Date Range', presetId: 'dashRangeFilter', hidePreset: true, hideContainerId: 'dashCustomRange' },
    { fromId: 'abDateFrom', toId: 'abDateTo', label: 'Date Range', presetId: 'abRangeFilter', hidePreset: true, hideContainerId: 'abCustomRange' },
    { fromId: 'reportDateFrom', toId: 'reportDateTo', label: 'Date Range', presetId: 'reportRangePreset', hidePreset: true, hideContainerId: 'reportCustomRange', autoApplyId: 'applyReportFilter' },
    { fromId: 'teamDateFrom', toId: 'teamDateTo', label: 'Date Range', presetId: 'teamRangePreset', hidePreset: true, hideContainerId: 'teamCustomRange', autoApplyId: 'applyTeamFilter' },
    { fromId: 'filterDateFrom', toId: 'filterDateTo', label: '', triggerPrefix: 'Date Range', hidePreset: true },
    { fromId: 'filterUpdatedFrom', toId: 'filterUpdatedTo', label: 'Status Updated Range', triggerPrefix: 'Updated' },
    { fromId: '_customDateFrom', toId: '_customDateTo', label: 'Custom Date Range' },
    { fromId: 'rqDateFrom', toId: 'rqDateTo', label: 'Date Range', mountId: 'rqDateRangeAnchor' },
    { fromId: 'exportDateFrom', toId: 'exportDateTo', label: 'Date Range' },
    { fromId: 'lsv2-logs-from', toId: 'lsv2-logs-to', label: 'Date Range' },
    { fromId: 'activityDateFrom', toId: 'activityDateTo', label: 'Date Range', onCommit: 'refreshActivityLogsDateRange' },
  ]

  var stateByKey = {}

  function pad2(n) { return n < 10 ? '0' + n : String(n) }

  function ymd(date) {
    return date.getFullYear() + '-' + pad2(date.getMonth() + 1) + '-' + pad2(date.getDate())
  }

  function toDate(v) {
    var s = String(v || '').trim()
    if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return null
    var p = s.split('-')
    var y = Number(p[0])
    var m = Number(p[1]) - 1
    var d = Number(p[2])
    if (!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(d)) return null
    return new Date(y, m, d)
  }

  function todayYmd() {
    var now = new Date()
    return ymd(new Date(now.getFullYear(), now.getMonth(), now.getDate()))
  }

  function formatLabel(v) {
    var d = toDate(v)
    if (!d) return ''
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  }

  function rangeLabel(from, to) {
    if (!from && !to) return 'All time'
    if (from && to) return formatLabel(from) + ' - ' + formatLabel(to)
    if (from) return formatLabel(from) + ' - Today'
    return 'Start - ' + formatLabel(to)
  }

  function monthStart(v) {
    var d = toDate(v) || new Date()
    return ymd(new Date(d.getFullYear(), d.getMonth(), 1))
  }

  function shiftMonth(v, off) {
    var d = toDate(v) || new Date()
    return ymd(new Date(d.getFullYear(), d.getMonth() + off, 1))
  }

  function monthLabel(v) {
    var d = toDate(v) || new Date()
    return d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
  }

  function presetRange(key) {
    var now = new Date()
    var start = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    var end = new Date(now.getFullYear(), now.getMonth(), now.getDate())

    if (key === 'today') {
      return { from: ymd(start), to: ymd(end) }
    }
    if (key === 'yesterday') {
      start.setDate(start.getDate() - 1)
      return { from: ymd(start), to: ymd(start) }
    }
    if (key === 'this-week') {
      start.setDate(start.getDate() - start.getDay())
      return { from: ymd(start), to: ymd(end) }
    }
    if (key === 'last-7-days') {
      start.setDate(start.getDate() - 6)
      return { from: ymd(start), to: ymd(end) }
    }
    if (key === 'last-week') {
      start.setDate(start.getDate() - start.getDay() - 7)
      end = new Date(start.getFullYear(), start.getMonth(), start.getDate())
      end.setDate(end.getDate() + 6)
      return { from: ymd(start), to: ymd(end) }
    }
    if (key === 'last-14-days') {
      start.setDate(start.getDate() - 13)
      return { from: ymd(start), to: ymd(end) }
    }
    if (key === 'this-month') {
      start = new Date(now.getFullYear(), now.getMonth(), 1)
      return { from: ymd(start), to: ymd(end) }
    }
    if (key === 'last-30-days') {
      start.setDate(start.getDate() - 29)
      return { from: ymd(start), to: ymd(end) }
    }
    if (key === 'last-month') {
      start = new Date(now.getFullYear(), now.getMonth() - 1, 1)
      end = new Date(now.getFullYear(), now.getMonth(), 0)
      return { from: ymd(start), to: ymd(end) }
    }
    if (key === 'all-time') {
      return { from: '', to: '' }
    }
    return { from: '', to: '' }
  }

  function detectPreset(from, to) {
    var f = String(from || '')
    var t = String(to || '')
    var i
    if (!f && !t) return 'all-time'
    for (i = 0; i < PRESETS.length; i += 1) {
      var key = PRESETS[i][0]
      if (key === 'all-time') continue
      var r = presetRange(key)
      if (r.from === f && r.to === t) return key
    }
    return 'custom'
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
  }

  function buildMonthGrid(key, monthYmd, draftFrom, draftTo) {
    var md = toDate(monthYmd) || new Date()
    var y = md.getFullYear()
    var m = md.getMonth()
    var first = new Date(y, m, 1).getDay()
    var days = new Date(y, m + 1, 0).getDate()
    var cells = []
    var d
    var today = todayYmd()

    for (d = 0; d < first; d += 1) cells.push('<span class="smdr-pad"></span>')

    for (d = 1; d <= days; d += 1) {
      var dd = new Date(y, m, d)
      var v = ymd(dd)
      var cls = ['smdr-day']
      var isFuture = v > today
      if (v === today) cls.push('today')
      if (draftFrom && draftTo && v >= draftFrom && v <= draftTo) cls.push('in-range')
      if (draftFrom && v === draftFrom) cls.push('start')
      if (draftTo && v === draftTo) cls.push('end')
      if (isFuture) cls.push('disabled')
      cells.push('<button type="button" class="' + cls.join(' ') + '" data-smdr-key="' + key + '" data-smdr-act="day" data-smdr-date="' + v + '" ' + (isFuture ? 'disabled aria-disabled="true"' : '') + '>' + d + '</button>')
    }

    return '' +
      '<div class="smdr-month" data-smdr-month="' + monthYmd + '">' +
        '<div class="smdr-month-title">' + escapeHtml(monthLabel(monthYmd)) + '</div>' +
        '<div class="smdr-weekdays"><span>Sun</span><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span></div>' +
        '<div class="smdr-grid">' + cells.join('') + '</div>' +
      '</div>'
  }

  function buildMonthStack(key, anchorYmd, draftFrom, draftTo) {
    var end = monthStart(todayYmd())
    var start = shiftMonth(end, -11)
    var anchor = monthStart(anchorYmd || end)
    if (anchor < start) start = anchor
    var cursor = start
    var parts = []
    var guard = 0
    while (cursor <= end && guard < 36) {
      parts.push(buildMonthGrid(key, cursor, draftFrom, draftTo))
      cursor = shiftMonth(cursor, 1)
      guard += 1
    }
    return parts.join('')
  }

  function ensureStyles() {
    if (document.getElementById('smDateRangeUpgradeStyles')) return
    var style = document.createElement('style')
    style.id = 'smDateRangeUpgradeStyles'
    style.textContent = [
      '.smdr-shell{position:relative;display:block;min-width:190px}',
      '.smdr-field{display:flex;flex-direction:column;gap:6px;min-width:190px}',
      '.smdr-label{font-size:11px;font-weight:800;letter-spacing:.3px;text-transform:uppercase;color:#64748b;line-height:1}',
      '.smdr-trigger{min-width:190px;max-width:100%;justify-content:space-between;display:inline-flex;align-items:center;gap:10px;height:36px;padding:0 12px;border-radius:10px;border:1px solid #cfd9e6;background:#fff;color:#111827;font-weight:700;cursor:pointer}',
      '.smdr-trigger:hover{border-color:#b9c7d8;box-shadow:0 6px 14px rgba(15,23,42,.08)}',
      '.smdr-trigger-text{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.smdr-pop{display:none;position:fixed;z-index:1300;border:1px solid #d8e2ef;border-radius:12px;background:#fff;box-shadow:0 12px 26px rgba(15,23,42,.12);overflow:hidden;max-height:calc(100vh - 24px)}',
      '.smdr-pop.open{display:block}',
      '.smdr-layout{display:grid;grid-template-columns:160px minmax(0,1fr)}',
      '.smdr-presets{padding:8px;background:#f8fafc;border-right:1px solid #e2e8f0;overflow:auto}',
      '.smdr-sidehead{margin:0 0 8px;color:#64748b;font-size:11px;font-weight:800;letter-spacing:.4px;text-transform:uppercase}',
      '.smdr-preset{width:100%;border:0;background:transparent;border-radius:8px;padding:7px 8px;font-size:12px;font-weight:700;color:#334155;text-align:left;cursor:pointer}',
      '.smdr-preset:hover{background:#e8f1ff;color:#1d4ed8}',
      '.smdr-preset.active{background:#dbeafe;color:#1d4ed8}',
      '.smdr-cal-area{padding:10px 11px 11px;display:flex;flex-direction:column;gap:8px;min-width:0}',
      '.smdr-head{display:flex;align-items:center;justify-content:flex-start;gap:8px;padding:2px 0 1px}',
      '.smdr-head-title{font-size:12px;color:#64748b;font-weight:700}',
      '.smdr-cals{display:flex;flex-direction:column;gap:10px;overflow-y:auto;max-height:340px;padding-right:2px;overscroll-behavior:contain}',
      '.smdr-month{border:1px solid #e2e8f0;border-radius:11px;padding:8px;background:#fff;min-width:0;overflow:hidden;flex:0 0 auto;height:auto}',
      '.smdr-month-title{font-size:11px;font-weight:800;color:#334155;margin-bottom:6px;text-align:center}',
      '.smdr-weekdays,.smdr-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:3px}',
      '.smdr-weekdays span{font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.2px;color:#94a3b8;text-align:center;padding:1px 0;white-space:nowrap;overflow:hidden}',
      '.smdr-pad{height:28px}',
      '.smdr-day{height:28px;width:100%;min-width:0;padding:0;border:0;border-radius:999px;background:transparent;color:#1f2937;font-size:11px;font-weight:700;line-height:1;display:flex;align-items:center;justify-content:center;cursor:pointer}',
      '.smdr-day:hover{background:#e8f1ff;color:#1d4ed8}',
      '.smdr-day.disabled,.smdr-day:disabled{background:#f8fafc;color:#94a3b8;cursor:not-allowed;opacity:.9}',
      '.smdr-day.disabled:hover,.smdr-day:disabled:hover{background:#f8fafc;color:#94a3b8}',
      '.smdr-day.today{box-shadow:inset 0 0 0 1px #cbd5e1}',
      '.smdr-day.in-range{background:#e0f2fe;border-radius:8px}',
      '.smdr-day.start,.smdr-day.end{background:#0f766e;color:#fff}',
      '.smdr-actions{display:flex;justify-content:flex-end;align-items:center;gap:8px;flex-wrap:wrap;border-top:1px solid #e2e8f0;padding-top:10px;margin-top:4px}',
      '.smdr-actions .lsv2-btn{min-width:72px}',
      '@media (max-width:768px){.smdr-layout{grid-template-columns:1fr}.smdr-presets{border-right:0;border-bottom:1px solid #e2e8f0}.smdr-cals{max-height:300px}}',
    ].join('')
    document.head.appendChild(style)
  }

  function dispatchChange(el) {
    if (!el) return
    try { el.dispatchEvent(new Event('input', { bubbles: true })) } catch (_e) {}
    try { el.dispatchEvent(new Event('change', { bubbles: true })) } catch (_e2) {}
  }

  function toLegacyPreset(newKey) {
    var entries = Object.keys(LEGACY_PRESET_MAP)
    var i
    for (i = 0; i < entries.length; i += 1) {
      var k = entries[i]
      if (LEGACY_PRESET_MAP[k] === newKey) return k
    }
    return 'custom'
  }

  function getState(key, fromEl, toEl) {
    if (!stateByKey[key]) {
      var from = String((fromEl && fromEl.value) || '').trim()
      var to = String((toEl && toEl.value) || '').trim()
      stateByKey[key] = {
        open: false,
        from: from,
        to: to,
        draftFrom: from,
        draftTo: to,
        anchor: monthStart(from || todayYmd()),
      }
    }
    return stateByKey[key]
  }

  function closeAllOpen(exceptKey) {
    Object.keys(stateByKey).forEach(function (k) {
      if (k === exceptKey) return
      var st = stateByKey[k]
      if (!st || !st.open) return
      st.open = false
      var host = document.querySelector('[data-smdr-key="' + k + '"]')
      if (host) rerender(k, host)
    })
  }

  function updatePosition(host, pop) {
    var trigger = host.querySelector('.smdr-trigger')
    if (!trigger || !pop) return
    var rect = trigger.getBoundingClientRect()
    var vw = window.innerWidth || document.documentElement.clientWidth || 0
    var width = Math.max(460, Math.min(560, vw - 24))
    var left = Math.max(12, Math.min(Math.round(rect.left), Math.max(12, vw - width - 12)))
    var top = Math.round(rect.bottom + 6)
    pop.style.left = left + 'px'
    pop.style.top = top + 'px'
    pop.style.width = width + 'px'
    pop.style.maxHeight = Math.max(240, (window.innerHeight || 0) - top - 16) + 'px'
  }

  function rerender(key, host) {
    var state = stateByKey[key]
    if (!state || !host) return
    var triggerText = host.querySelector('.smdr-trigger-text')
    if (triggerText) {
      var base = rangeLabel(state.from, state.to)
      var prefix = state.cfg && state.cfg.triggerPrefix ? String(state.cfg.triggerPrefix) : ''
      triggerText.textContent = prefix ? (prefix + ': ' + base) : base
    }
    var pop = host.querySelector('.smdr-pop')
    if (pop) {
      pop.classList.toggle('open', !!state.open)
      if (state.open) updatePosition(host, pop)
    }

    var presetKey = detectPreset(state.draftFrom, state.draftTo)
    host.querySelectorAll('.smdr-preset').forEach(function (btn) {
      btn.classList.toggle('active', String(btn.getAttribute('data-smdr-preset') || '') === presetKey)
    })

    var cals = host.querySelector('.smdr-cals')
    if (cals) {
      cals.innerHTML = buildMonthStack(key, state.anchor, state.draftFrom, state.draftTo)
      if (state.open) {
        var targetMonth = monthStart(state.draftFrom || state.from || todayYmd())
        var target = cals.querySelector('[data-smdr-month="' + targetMonth + '"]')
        if (target && typeof target.scrollIntoView === 'function') {
          target.scrollIntoView({ block: 'center' })
        }
      }
    }
  }

  function commitState(cfg, key, host, triggerApply) {
    var fromEl = document.getElementById(cfg.fromId)
    var toEl = document.getElementById(cfg.toId)
    var presetEl = cfg.presetId ? document.getElementById(cfg.presetId) : null
    var state = stateByKey[key]
    if (!state) return

    state.from = state.draftFrom
    state.to = state.draftTo

    if (presetEl) {
      var preset = detectPreset(state.from, state.to)
      presetEl.value = toLegacyPreset(preset)
      dispatchChange(presetEl)
    }

    if (fromEl) fromEl.value = state.from
    if (toEl) toEl.value = state.to
    dispatchChange(fromEl)
    dispatchChange(toEl)

    if (triggerApply && cfg.autoApplyId) {
      var applyBtn = document.getElementById(cfg.autoApplyId)
      if (applyBtn && !applyBtn.disabled) applyBtn.click()
    }

    if (cfg.fromId === 'rqDateFrom') {
      var modeEl = document.getElementById('rqStaleMode')
      if (modeEl && modeEl.value !== 'custom') modeEl.value = 'custom'
      var rqApply = document.getElementById('rqApplyDateRange')
      if (rqApply && !rqApply.disabled) {
        rqApply.click()
      } else if (typeof window._rqLoad === 'function') {
        try { window._rqLoad() } catch (_e2) {}
      }
    }

    if (cfg.onCommit && typeof window[cfg.onCommit] === 'function') {
      try { window[cfg.onCommit](state.from, state.to) } catch (_e) {}
    }

    state.open = false
    rerender(key, host)
  }

  function setupControl(cfg) {
    var fromEl = document.getElementById(cfg.fromId)
    var toEl = document.getElementById(cfg.toId)
    if (!fromEl || !toEl) return

    var key = cfg.fromId + '__' + cfg.toId
    if (document.querySelector('[data-smdr-key="' + key + '"]')) return

    var fromWrap = fromEl.closest('.dash-filter-group, .lsv2-logs-field, .rq-filter-field') || fromEl.parentElement
    var toWrap = toEl.closest('.dash-filter-group, .lsv2-logs-field, .rq-filter-field') || toEl.parentElement
    if (!fromWrap || !toWrap) return

    ensureStyles()
    var state = getState(key, fromEl, toEl)
    state.cfg = cfg

    var shell = document.createElement('div')
    shell.className = 'smdr-shell'
    shell.setAttribute('data-smdr-key', key)
    shell.innerHTML = '' +
      '<button type="button" class="smdr-trigger">' +
        '<span class="smdr-trigger-text"></span>' +
        '<span aria-hidden="true">v</span>' +
      '</button>' +
      '<div class="smdr-pop">' +
        '<div class="smdr-layout">' +
          '<div class="smdr-presets">' +
            '<div class="smdr-sidehead">Presets</div>' +
            PRESETS.map(function (p) {
              return '<button type="button" class="smdr-preset" data-smdr-key="' + key + '" data-smdr-act="preset" data-smdr-preset="' + p[0] + '">' + escapeHtml(p[1]) + '</button>'
            }).join('') +
          '</div>' +
          '<div class="smdr-cal-area">' +
            '<div class="smdr-head"><div class="smdr-head-title">Select a start and end date</div></div>' +
            '<div class="smdr-cals"></div>' +
            '<div class="smdr-actions">' +
              '<button type="button" class="lsv2-btn subtle" data-smdr-key="' + key + '" data-smdr-act="clear">Clear</button>' +
              '<button type="button" class="lsv2-btn subtle" data-smdr-key="' + key + '" data-smdr-act="cancel">Cancel</button>' +
              '<button type="button" class="lsv2-btn primary" data-smdr-key="' + key + '" data-smdr-act="apply">Apply</button>' +
            '</div>' +
          '</div>' +
        '</div>' +
      '</div>'

    var field = document.createElement('div')
    field.className = 'smdr-field'
    field.setAttribute('data-smdr-key', key)
    if (cfg.label) {
      var label = document.createElement('div')
      label.className = 'smdr-label'
      label.textContent = String(cfg.label)
      field.appendChild(label)
    }
    field.appendChild(shell)

    if (cfg.mountId) {
      var mount = document.getElementById(cfg.mountId)
      if (mount) {
        mount.appendChild(field)
      } else {
        fromWrap.parentNode.insertBefore(field, fromWrap)
      }
    } else {
      fromWrap.parentNode.insertBefore(field, fromWrap)
    }

    fromWrap.style.display = 'none'
    toWrap.style.display = 'none'

    if (cfg.hideContainerId) {
      var hc = document.getElementById(cfg.hideContainerId)
      if (hc) hc.style.display = 'none'
    }

    if (cfg.hidePreset && cfg.presetId) {
      var presetEl = document.getElementById(cfg.presetId)
      var presetWrap = presetEl ? (presetEl.closest('.dash-filter-group, .lsv2-logs-field, .rq-filter-field') || presetEl.parentElement) : null
      if (presetWrap) presetWrap.style.display = 'none'
    }

    shell.addEventListener('click', function (ev) {
      ev.stopPropagation()
      var target = ev.target
      if (!target) return
      var action = String(target.getAttribute('data-smdr-act') || '')
      var st = stateByKey[key]
      if (!st) return

      if (target.classList.contains('smdr-trigger') || target.closest('.smdr-trigger')) {
        closeAllOpen(key)
        st.draftFrom = st.from
        st.draftTo = st.to
        st.anchor = monthStart(st.draftFrom || todayYmd())
        st.open = !st.open
        rerender(key, shell)
        return
      }

      if (!action) return

      if (action === 'preset') {
        var preset = String(target.getAttribute('data-smdr-preset') || '')
        var r = presetRange(preset)
        st.draftFrom = r.from
        st.draftTo = r.to
        st.anchor = monthStart(st.draftFrom || todayYmd())
        rerender(key, shell)
        return
      }

      if (action === 'day') {
        if (target.disabled || target.classList.contains('disabled')) return
        var y = String(target.getAttribute('data-smdr-date') || '')
        if (!st.draftFrom || (st.draftFrom && st.draftTo)) {
          st.draftFrom = y
          st.draftTo = ''
        } else if (y < st.draftFrom) {
          st.draftTo = st.draftFrom
          st.draftFrom = y
        } else {
          st.draftTo = y
        }
        st.anchor = monthStart(st.draftFrom || y)
        rerender(key, shell)
        return
      }

      if (action === 'clear') {
        st.draftFrom = ''
        st.draftTo = ''
        commitState(cfg, key, shell, true)
        return
      }

      if (action === 'cancel') {
        st.open = false
        rerender(key, shell)
        return
      }

      if (action === 'apply') {
        commitState(cfg, key, shell, true)
      }
    })

    rerender(key, shell)
  }

  function closeAllOutside(ev) {
    var inside = ev.target && ev.target.closest ? ev.target.closest('.smdr-shell') : null
    if (inside) return
    Object.keys(stateByKey).forEach(function (k) {
      var st = stateByKey[k]
      if (!st || !st.open) return
      st.open = false
      var host = document.querySelector('[data-smdr-key="' + k + '"]')
      if (host) rerender(k, host)
    })
  }

  function runUpgrade() {
    CONFIGS.forEach(setupControl)
  }

  var upgradeTimer = null
  function scheduleRunUpgrade(delayMs) {
    if (upgradeTimer) clearTimeout(upgradeTimer)
    upgradeTimer = setTimeout(function () {
      upgradeTimer = null
      runUpgrade()
    }, Number.isFinite(delayMs) ? delayMs : 80)
  }

  window.smUpgradeDateRangeFilters = runUpgrade

  document.addEventListener('pointerdown', closeAllOutside)
  window.addEventListener('resize', function () { scheduleRunUpgrade(120) })
  window.addEventListener('popstate', function () { scheduleRunUpgrade(20) })
  window.addEventListener('hashchange', function () { scheduleRunUpgrade(20) })

  var _origPushState = history.pushState
  history.pushState = function () {
    var out = _origPushState.apply(this, arguments)
    scheduleRunUpgrade(20)
    return out
  }

  var _origReplaceState = history.replaceState
  history.replaceState = function () {
    var out = _origReplaceState.apply(this, arguments)
    scheduleRunUpgrade(20)
    return out
  }

  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', function () { runUpgrade() })
  } else {
    runUpgrade()
  }
})()
