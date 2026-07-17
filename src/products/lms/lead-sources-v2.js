// ============================================================================
// Lead Sources V2 - route-driven UX for LMS
// ============================================================================

(function () {
  var LS_V2_VIEWS = ['sources', 'connect', 'forms', 'validation', 'logs', 'reports']
  var _lsv2ReportCache = Object.create(null)
  var _lsv2ReportInFlight = Object.create(null)
  var _lsv2ReportCacheTtlMs = 15000

  function _lsv2Esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
  }

  function _lsv2ReadJsonSafe(res) {
    return res.json().catch(function () { return {} })
  }

  function _lsv2ReportCacheClear() {
    _lsv2ReportCache = Object.create(null)
    _lsv2ReportInFlight = Object.create(null)
  }

  async function _lsv2FetchReport(url) {
    var now = Date.now()
    var cached = _lsv2ReportCache[url]
    if (cached && (now - cached.ts) < _lsv2ReportCacheTtlMs) {
      return cached.payload
    }
    if (_lsv2ReportInFlight[url]) return _lsv2ReportInFlight[url]
    _lsv2ReportInFlight[url] = (async function () {
      var res = await authFetch(url)
      var data = await _lsv2ReadJsonSafe(res)
      var payload = { ok: res.ok, status: res.status, data: data }
      if (res.ok) _lsv2ReportCache[url] = { ts: Date.now(), payload: payload }
      delete _lsv2ReportInFlight[url]
      return payload
    })().catch(function (err) {
      delete _lsv2ReportInFlight[url]
      throw err
    })
    return _lsv2ReportInFlight[url]
  }

  async function _lsv2DownloadFile(url, fallbackName) {
    var res = await authFetch(url)
    if (!res.ok) {
      var err = await _lsv2ReadJsonSafe(res)
      alert(err.error || 'Export failed')
      return
    }
    var blob = await res.blob()
    var cd = String(res.headers.get('content-disposition') || '')
    var m = cd.match(/filename=([^;]+)/i)
    var filename = (m && m[1] ? m[1] : (fallbackName || 'download.csv')).replace(/"/g, '')
    var objUrl = URL.createObjectURL(blob)
    var a = document.createElement('a')
    a.href = objUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(function () { URL.revokeObjectURL(objUrl) }, 500)
  }

  function _lsv2ApiHref(path) {
    var p = String(path || '')
    var apiBase = (typeof API_BASE === 'string' ? API_BASE : '')
    var hostBase = apiBase ? apiBase.replace(/\/api\/?$/, '') : ''
    if (!hostBase) return p
    return hostBase + p
  }

  function _lsv2ShowTestDataEnabled() {
    return String(window._LS_V2_SHOW_TEST_DATA || '').toLowerCase() === '1'
      || String(window._LS_V2_SHOW_TEST_DATA || '').toLowerCase() === 'true'
      || String(window._LS_V2_SHOW_TEST_DATA || '').toLowerCase() === 'yes'
      || String(window._LS_V2_SHOW_TEST_DATA || '').toLowerCase() === 'on'
  }

  function _lsv2SetShowTestData(enabled) {
    window._LS_V2_SHOW_TEST_DATA = enabled ? '1' : ''
  }

  function _lsv2Pad2(n) {
    return String(n < 10 ? '0' + n : n)
  }

  function _lsv2DateToYmd(date) {
    return date.getFullYear() + '-' + _lsv2Pad2(date.getMonth() + 1) + '-' + _lsv2Pad2(date.getDate())
  }

  function _lsv2YmdToDate(ymd) {
    var parts = String(ymd || '').split('-')
    if (parts.length !== 3) return null
    var year = Number(parts[0])
    var month = Number(parts[1]) - 1
    var day = Number(parts[2])
    if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null
    return new Date(year, month, day)
  }

  function _lsv2FormatDateLabel(ymd) {
    var date = _lsv2YmdToDate(ymd)
    if (!date) return ''
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  }

  function _lsv2TodayYmd() {
    return _lsv2DateToYmd(new Date())
  }

  function _lsv2ReportRangeLabel(dateFrom, dateTo) {
    if (!dateFrom && !dateTo) return 'All time'
    if (dateFrom && dateTo) return _lsv2FormatDateLabel(dateFrom) + ' - ' + _lsv2FormatDateLabel(dateTo)
    if (dateFrom) return _lsv2FormatDateLabel(dateFrom) + ' - Today'
    return 'Start - ' + _lsv2FormatDateLabel(dateTo)
  }

  function _lsv2ReportRangePresetRange(preset) {
    var today = new Date()
    var start = new Date(today.getFullYear(), today.getMonth(), today.getDate())
    var end = new Date(today.getFullYear(), today.getMonth(), today.getDate())
    var label = 'Custom'

    if (preset === 'today') {
      label = 'Today'
    } else if (preset === 'yesterday') {
      start.setDate(start.getDate() - 1)
      end = new Date(start.getFullYear(), start.getMonth(), start.getDate())
      label = 'Yesterday'
    } else if (preset === 'this-week') {
      var day = start.getDay()
      start.setDate(start.getDate() - day)
      label = 'This week (Sun - Today)'
    } else if (preset === 'last-7-days') {
      start.setDate(start.getDate() - 6)
      label = 'Last 7 days'
    } else if (preset === 'last-week') {
      var thisWeekDay = start.getDay()
      start.setDate(start.getDate() - thisWeekDay - 7)
      end = new Date(start.getFullYear(), start.getMonth(), start.getDate())
      end.setDate(end.getDate() + 6)
      label = 'Last week (Sun - Sat)'
    } else if (preset === 'last-14-days') {
      start.setDate(start.getDate() - 13)
      label = 'Last 14 days'
    } else if (preset === 'this-month') {
      start = new Date(today.getFullYear(), today.getMonth(), 1)
      label = 'This month'
    } else if (preset === 'last-30-days') {
      start.setDate(start.getDate() - 29)
      label = 'Last 30 days'
    } else if (preset === 'last-month') {
      start = new Date(today.getFullYear(), today.getMonth() - 1, 1)
      end = new Date(today.getFullYear(), today.getMonth(), 0)
      label = 'Last month'
    } else if (preset === 'all-time') {
      start = null
      end = null
      label = 'All time'
    }

    return {
      from: start ? _lsv2DateToYmd(start) : '',
      to: end ? _lsv2DateToYmd(end) : '',
      label: label,
    }
  }

  function _lsv2ReportRangePresetKey(dateFrom, dateTo) {
    var from = String(dateFrom || '').trim()
    var to = String(dateTo || '').trim()
    var today = _lsv2TodayYmd()
    var preset

    if (!from && !to) return 'all-time'
    preset = _lsv2ReportRangePresetRange('today')
    if (from === preset.from && to === preset.to) return 'today'
    preset = _lsv2ReportRangePresetRange('yesterday')
    if (from === preset.from && to === preset.to) return 'yesterday'
    preset = _lsv2ReportRangePresetRange('this-week')
    if (from === preset.from && to === preset.to) return 'this-week'
    preset = _lsv2ReportRangePresetRange('last-7-days')
    if (from === preset.from && to === preset.to) return 'last-7-days'
    preset = _lsv2ReportRangePresetRange('last-week')
    if (from === preset.from && to === preset.to) return 'last-week'
    preset = _lsv2ReportRangePresetRange('last-14-days')
    if (from === preset.from && to === preset.to) return 'last-14-days'
    preset = _lsv2ReportRangePresetRange('this-month')
    if (from === preset.from && to === preset.to) return 'this-month'
    preset = _lsv2ReportRangePresetRange('last-30-days')
    if (from === preset.from && to === preset.to) return 'last-30-days'
    preset = _lsv2ReportRangePresetRange('last-month')
    if (from === preset.from && to === preset.to) return 'last-month'
    if (from === today && to === today) return 'today'
    return 'custom'
  }

  function _lsv2ReportRangeKey(kind, suffix) {
    return '_LS_V2_REPORTS_' + (kind === 'source' ? 'SOURCE' : 'CAMPAIGN') + '_' + suffix
  }

  function _lsv2ReportRangeSet(kind, suffix, value) {
    window[_lsv2ReportRangeKey(kind, suffix)] = String(value == null ? '' : value)
  }

  function _lsv2ReportRangeGet(kind, suffix) {
    return String(window[_lsv2ReportRangeKey(kind, suffix)] || '').trim()
  }

  function _lsv2ReportRangeOpen(kind, open) {
    window[_lsv2ReportRangeKey(kind, 'RANGE_OPEN')] = open ? '1' : ''
  }

  function _lsv2ReportRangeIsOpen(kind) {
    return String(window[_lsv2ReportRangeKey(kind, 'RANGE_OPEN')] || '') === '1'
  }

  function _lsv2ReportRangeInitDraft(kind) {
    _lsv2ReportRangeSet(kind, 'DRAFT_DATE_FROM', _lsv2ReportRangeGet(kind, 'DATE_FROM'))
    _lsv2ReportRangeSet(kind, 'DRAFT_DATE_TO', _lsv2ReportRangeGet(kind, 'DATE_TO'))
  }

  function _lsv2ReportRangeDraftValue(kind, suffix, fallback) {
    var value = _lsv2ReportRangeGet(kind, 'DRAFT_' + suffix)
    return value || String(fallback || '')
  }

  function _lsv2ReportRangeApply(kind) {
    _lsv2ReportRangeSet(kind, 'DATE_FROM', _lsv2ReportRangeGet(kind, 'DRAFT_DATE_FROM'))
    _lsv2ReportRangeSet(kind, 'DATE_TO', _lsv2ReportRangeGet(kind, 'DRAFT_DATE_TO'))
    _lsv2ReportRangeSet(kind, 'PAGE', 1)
    _lsv2ReportRangeOpen(kind, false)
    _lsv2RenderReports()
  }

  function _lsv2ReportRangeClear(kind) {
    _lsv2ReportRangeSet(kind, 'DATE_FROM', '')
    _lsv2ReportRangeSet(kind, 'DATE_TO', '')
    _lsv2ReportRangeSet(kind, 'DRAFT_DATE_FROM', '')
    _lsv2ReportRangeSet(kind, 'DRAFT_DATE_TO', '')
    _lsv2ReportRangeSet(kind, 'PAGE', 1)
    _lsv2ReportRangeOpen(kind, false)
    _lsv2RenderReports()
  }

  function _lsv2ReportRangeSetPreset(kind, preset) {
    var range = _lsv2ReportRangePresetRange(preset)
    _lsv2ReportRangeSet(kind, 'DRAFT_DATE_FROM', range.from)
    _lsv2ReportRangeSet(kind, 'DRAFT_DATE_TO', range.to)
    _lsv2ReportRangeOpen(kind, true)
    _lsv2ReportRangeSyncUi(kind)
  }

  function _lsv2ReportRangePresetClick(btn) {
    if (!btn) return
    _lsv2ReportRangeSetPreset(String(btn.getAttribute('data-range-kind') || 'source'), String(btn.getAttribute('data-range-preset') || 'custom'))
  }

  function _lsv2ReportRangeDayClick(btn) {
    if (!btn) return
    _lsv2ReportRangeSetDraftDate(String(btn.getAttribute('data-range-kind') || 'source'), String(btn.getAttribute('data-range-date') || ''))
  }

  function _lsv2ReportRangeMonthClick(btn) {
    if (!btn) return
    _lsv2ReportRangeSetMonth(String(btn.getAttribute('data-range-kind') || 'source'), String(btn.getAttribute('data-range-month') || '') === 'prev' ? -1 : 1)
  }

  // Inline calendar handlers are referenced from HTML attributes; expose them globally.
  window._lsv2ReportRangePresetClick = _lsv2ReportRangePresetClick
  window._lsv2ReportRangeDayClick = _lsv2ReportRangeDayClick
  window._lsv2ReportRangeMonthClick = _lsv2ReportRangeMonthClick

  function _lsv2MonthStartYmd(ymd) {
    var date = _lsv2YmdToDate(ymd) || new Date()
    return _lsv2DateToYmd(new Date(date.getFullYear(), date.getMonth(), 1))
  }

  function _lsv2ShiftMonthYmd(ymd, offset) {
    var date = _lsv2YmdToDate(ymd) || new Date()
    return _lsv2DateToYmd(new Date(date.getFullYear(), date.getMonth() + offset, 1))
  }

  function _lsv2CalendarMonthLabel(date) {
    return date.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
  }

  function _lsv2CalendarDayNames() {
    return ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  }

  function _lsv2CalendarMonthHtml(kind, monthYmd, draftFrom, draftTo) {
    var monthDate = _lsv2YmdToDate(monthYmd) || new Date()
    var year = monthDate.getFullYear()
    var month = monthDate.getMonth()
    var firstDay = new Date(year, month, 1).getDay()
    var daysInMonth = new Date(year, month + 1, 0).getDate()
    var todayYmd = _lsv2TodayYmd()
    var cells = []
    var day

    for (day = 0; day < firstDay; day += 1) {
      cells.push('<span class="lsv2-date-calendar-pad"></span>')
    }

    for (day = 1; day <= daysInMonth; day += 1) {
      var cellDate = new Date(year, month, day)
      var ymd = _lsv2DateToYmd(cellDate)
      var classes = ['lsv2-date-calendar-day']
      var isFuture = ymd > todayYmd
      if (ymd === todayYmd) classes.push('today')
      if (draftFrom && draftTo && ymd >= draftFrom && ymd <= draftTo) classes.push('in-range')
      if (draftFrom && ymd === draftFrom) classes.push('start')
      if (draftTo && ymd === draftTo) classes.push('end')
      if (isFuture) classes.push('disabled')
      cells.push('<button type="button" class="' + classes.join(' ') + '" data-range-kind="' + kind + '" data-range-date="' + ymd + '" aria-label="' + _lsv2Esc(cellDate.toDateString()) + '" ' + (isFuture ? 'disabled aria-disabled="true"' : '') + '>' + day + '</button>')
      cells[cells.length - 1] = cells[cells.length - 1].replace('<button type="button"', '<button type="button" onclick="_lsv2ReportRangeDayClick(this)"')
    }

    return '' +
      '<div class="lsv2-date-calendar-month" data-lsv2-month="' + monthYmd + '">' +
        '<div class="lsv2-date-calendar-month-title">' + _lsv2Esc(_lsv2CalendarMonthLabel(monthDate)) + '</div>' +
        '<div class="lsv2-date-calendar-weekdays">' + _lsv2CalendarDayNames().map(function (name) { return '<span>' + name + '</span>' }).join('') + '</div>' +
        '<div class="lsv2-date-calendar-grid">' + cells.join('') + '</div>' +
      '</div>'
  }

  function _lsv2CalendarStackHtml(kind, anchorYmd, draftFrom, draftTo) {
    var end = _lsv2MonthStartYmd(_lsv2TodayYmd())
    var start = _lsv2ShiftMonthYmd(end, -11)
    var anchor = _lsv2MonthStartYmd(anchorYmd || end)
    if (anchor < start) start = anchor
    var cursor = start
    var parts = []
    var guard = 0
    while (cursor <= end && guard < 36) {
      parts.push(_lsv2CalendarMonthHtml(kind, cursor, draftFrom, draftTo))
      cursor = _lsv2ShiftMonthYmd(cursor, 1)
      guard += 1
    }
    return parts.join('')
  }

  function _lsv2ReportRangeSetDraftDate(kind, ymd) {
    if (!ymd || ymd > _lsv2TodayYmd()) return
    var from = _lsv2ReportRangeGet(kind, 'DRAFT_DATE_FROM')
    var to = _lsv2ReportRangeGet(kind, 'DRAFT_DATE_TO')

    if (!from || (from && to)) {
      _lsv2ReportRangeSet(kind, 'DRAFT_DATE_FROM', ymd)
      _lsv2ReportRangeSet(kind, 'DRAFT_DATE_TO', '')
    } else if (ymd < from) {
      _lsv2ReportRangeSet(kind, 'DRAFT_DATE_FROM', ymd)
      _lsv2ReportRangeSet(kind, 'DRAFT_DATE_TO', from)
    } else {
      _lsv2ReportRangeSet(kind, 'DRAFT_DATE_TO', ymd)
    }

    _lsv2ReportRangeSet(kind, 'MONTH_ANCHOR', _lsv2MonthStartYmd(_lsv2ReportRangeGet(kind, 'DRAFT_DATE_FROM') || ymd))
    _lsv2ReportRangeOpen(kind, true)
    _lsv2ReportRangeSyncUi(kind)
  }

  function _lsv2ReportRangeSetMonth(kind, offset) {
    var anchor = _lsv2ReportRangeGet(kind, 'MONTH_ANCHOR') || _lsv2MonthStartYmd(_lsv2ReportRangeGet(kind, 'DRAFT_DATE_FROM') || _lsv2TodayYmd())
    _lsv2ReportRangeSet(kind, 'MONTH_ANCHOR', _lsv2ShiftMonthYmd(anchor, offset))
    _lsv2ReportRangeOpen(kind, true)
    _lsv2ReportRangeSyncUi(kind)
  }

  function _lsv2ReportRangeSyncUi(kind) {
    var prefix = kind === 'source' ? 'source' : 'campaign'
    var trigger = document.getElementById('lsv2-reports-' + prefix + '-range-trigger')
    var popover = document.getElementById('lsv2-reports-' + prefix + '-picker-popover')
    var panel = document.getElementById('lsv2-reports-' + prefix + '-picker-panel')
    if (!trigger || !popover || !panel) return

    var committedFrom = _lsv2ReportRangeGet(kind, 'DATE_FROM')
    var committedTo = _lsv2ReportRangeGet(kind, 'DATE_TO')
    var draftFrom = _lsv2ReportRangeDraftValue(kind, 'DATE_FROM', committedFrom)
    var draftTo = _lsv2ReportRangeDraftValue(kind, 'DATE_TO', committedTo)
    var monthAnchor = _lsv2ReportRangeGet(kind, 'MONTH_ANCHOR') || _lsv2MonthStartYmd(draftFrom || committedFrom || _lsv2TodayYmd())
    var presetKey = _lsv2ReportRangePresetKey(draftFrom, draftTo)

    var triggerText = trigger.querySelector('span')
    if (triggerText) triggerText.textContent = _lsv2ReportRangeLabel(committedFrom, committedTo)

    popover.classList.add('open')
    trigger.setAttribute('aria-expanded', 'true')

    var calendars = panel.querySelector('.lsv2-date-picker-calendars')
    if (calendars) {
      calendars.innerHTML = _lsv2CalendarStackHtml(prefix, monthAnchor, draftFrom, draftTo)
      var targetMonth = _lsv2MonthStartYmd(draftFrom || committedFrom || _lsv2TodayYmd())
      var target = calendars.querySelector('[data-lsv2-month="' + targetMonth + '"]')
      if (target && typeof target.scrollIntoView === 'function') {
        target.scrollIntoView({ block: 'center' })
      }
    }

    panel.querySelectorAll('.lsv2-date-picker-preset').forEach(function (btn) {
      var preset = String(btn.getAttribute('data-range-preset') || '')
      var active = presetKey === preset || (!draftFrom && !draftTo && preset === 'all-time')
      btn.classList.toggle('active', !!active)
    })

    _lsv2ReportRangeUpdatePopoverPosition(kind)
  }

  function _lsv2ReportRangeUpdatePopoverPosition(kind) {
    var prefix = kind === 'source' ? 'source' : 'campaign'
    var trigger = document.getElementById('lsv2-reports-' + prefix + '-range-trigger')
    var popover = document.getElementById('lsv2-reports-' + prefix + '-picker-popover')
    if (!trigger || !popover) return
    var rect = trigger.getBoundingClientRect()
    var viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0
    var width = Math.max(460, Math.min(560, viewportWidth - 24))
    var left = Math.max(12, Math.min(Math.round(rect.left), Math.max(12, viewportWidth - width - 12)))
    var top = Math.round(rect.bottom + 6)
    popover.style.left = left + 'px'
    popover.style.top = top + 'px'
    popover.style.width = width + 'px'
    popover.style.maxHeight = Math.max(240, (window.innerHeight || 0) - top - 16) + 'px'
  }

  function _lsv2ReportRangeSetOpenUi(kind, open) {
    var prefix = kind === 'source' ? 'source' : 'campaign'
    var popover = document.getElementById('lsv2-reports-' + prefix + '-picker-popover')
    var trigger = document.getElementById('lsv2-reports-' + prefix + '-range-trigger')
    if (popover) popover.classList.toggle('open', !!open)
    if (trigger) trigger.setAttribute('aria-expanded', open ? 'true' : 'false')
  }

  function _lsv2ReportRangePanelHtml(kind, committedFrom, committedTo, showTestChecked, exportFormat, extraActionHtml) {
    var prefix = kind === 'source' ? 'source' : 'campaign'
    var isOpen = _lsv2ReportRangeIsOpen(kind)
    var draftFrom = _lsv2ReportRangeDraftValue(kind, 'DATE_FROM', committedFrom)
    var draftTo = _lsv2ReportRangeDraftValue(kind, 'DATE_TO', committedTo)
    var monthAnchor = _lsv2ReportRangeGet(kind, 'MONTH_ANCHOR') || _lsv2MonthStartYmd(draftFrom || committedFrom || _lsv2TodayYmd())
    var nextMonthAnchor = _lsv2ShiftMonthYmd(monthAnchor, 1)
    var triggerLabel = _lsv2ReportRangeLabel(committedFrom, committedTo)
    var presetKey = _lsv2ReportRangePresetKey(draftFrom, draftTo)
    var presets = [
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
    var presetHtml = presets.map(function (item) {
      var active = presetKey === item[0] || (!draftFrom && !draftTo && item[0] === 'all-time')
      return '<button type="button" class="lsv2-date-picker-preset' + (active ? ' active' : '') + '" data-range-kind="' + prefix + '" data-range-preset="' + item[0] + '" onclick="_lsv2ReportRangePresetClick(this)">' + _lsv2Esc(item[1]) + '</button>'
    }).join('')

    return '' +
      '<div class="lsv2-reports-date-shell">' +
        '<div class="lsv2-reports-date-toolbar">' +
          '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">' +
            '<button type="button" id="lsv2-reports-' + prefix + '-range-trigger" class="lsv2-btn subtle lsv2-date-trigger" aria-expanded="' + (isOpen ? 'true' : 'false') + '">' +
              '<span>' + _lsv2Esc(triggerLabel) + '</span>' +
              '<span aria-hidden="true">▾</span>' +
            '</button>' +
            '<label class="lsv2-logs-filter-toggle" style="margin:0">' +
              '<input id="lsv2-reports-' + prefix + '-show-test" type="checkbox" ' + (showTestChecked ? 'checked' : '') + '> Show Test Data' +
            '</label>' +
          '</div>' +
          '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-left:auto">' +
            (extraActionHtml || '') +
            '<select id="lsv2-reports-' + prefix + '-export-format" class="form-select form-select-sm lsv2-input-compact" style="width:auto;min-width:120px"><option value="csv" ' + (String(exportFormat || 'csv') === 'csv' ? 'selected' : '') + '>CSV</option><option value="xlsx" ' + (String(exportFormat || 'csv') === 'xlsx' ? 'selected' : '') + '>XLSX</option></select>' +
            '<button id="lsv2-reports-' + prefix + '-export-btn" class="lsv2-btn subtle">Download</button>' +
          '</div>' +
        '</div>' +
        '<div id="lsv2-reports-' + prefix + '-picker-popover" class="lsv2-date-picker-popover' + (isOpen ? ' open' : '') + '">' +
          '<div id="lsv2-reports-' + prefix + '-picker-panel" class="lsv2-date-picker-layout">' +
            '<div class="lsv2-date-picker-presets">' +
              '<div class="lsv2-date-picker-sidehead">Presets</div>' +
              presetHtml +
            '</div>' +
            '<div class="lsv2-date-picker-calendar-area">' +
              '<div class="lsv2-date-picker-calendar-head"><div class="lsv2-muted">Select a start and end date</div></div>' +
              '<div class="lsv2-date-picker-calendars">' +
                _lsv2CalendarStackHtml(prefix, monthAnchor, draftFrom, draftTo) +
              '</div>' +
              '<div class="lsv2-date-picker-actions">' +
                '<button id="lsv2-reports-' + prefix + '-clear-btn" type="button" class="lsv2-btn subtle">Clear</button>' +
                '<button id="lsv2-reports-' + prefix + '-cancel-btn" type="button" class="lsv2-btn subtle">Cancel</button>' +
                '<button id="lsv2-reports-' + prefix + '-apply-btn" type="button" class="lsv2-btn primary">Apply</button>' +
              '</div>' +
            '</div>' +
          '</div>' +
        '</div>' +
      '</div>'
  }

  function _lsv2RenderReportRangePicker(kind, committedFrom, committedTo, showTestChecked, exportFormat, extraActionHtml) {
    return _lsv2ReportRangePanelHtml(kind, committedFrom, committedTo, showTestChecked, exportFormat, extraActionHtml)
  }

  function _lsv2ApplyTestDataParam(params) {
    if (_lsv2ShowTestDataEnabled()) {
      params.append('show_test_data', '1')
    }
  }

  function _lsv2LabelOr(value, fallback) {
    var text = String(value == null ? '' : value).trim()
    return text && text !== '-' ? text : fallback
  }

  function _lsv2ValidationInfo() {
    return {
      meta_connection: {
        title: 'Meta Connection',
        why: 'Confirms the source can authenticate and discover pages and forms.',
        fix: 'Reconnect the Meta source and re-check page and permission access.',
      },
      meta_lead_validation: {
        title: 'Meta Lead Validation',
        why: 'Verifies a live Meta lead can enter the LMS and write its downstream records.',
        fix: 'Check the Meta form mapping, lead permissions, and assignment rules.',
      },
      google_connection: {
        title: 'Google Connection',
        why: 'Confirms the source can authenticate and discover Google lead assets.',
        fix: 'Reconnect the Google source and verify the linked account permissions.',
      },
      google_lead_validation: {
        title: 'Google Lead Validation',
        why: 'Verifies a live Google lead can create a lead and supporting activity.',
        fix: 'Check Google form access, mapping, and ingestion rules.',
      },
    }
  }

  function _lsv2CurrentView() {
    var path = String(window.location.pathname || '')
    var pathMatch = path.match(/^\/apps\/[^\/]+\/[^\/]+\/lead-sources(?:\/([^\/]+))?$/)
    if (!pathMatch) {
      pathMatch = path.match(/^\/[^\/]+\/lead-sources(?:\/([^\/]+))?$/)
    }
    if (pathMatch) {
      var pv = String(pathMatch[1] || 'sources').trim().toLowerCase()
      if (pv === 'validate') pv = 'validation'
      if (LS_V2_VIEWS.indexOf(pv) >= 0) return pv
    }

    var v = String(window._LS_ROUTE_VIEW || '').trim().toLowerCase()
    if (v === 'validate') v = 'validation'
    if (LS_V2_VIEWS.indexOf(v) >= 0) return v
    return 'sources'
  }

  function _lsv2ViewIs(view) {
    return _lsv2CurrentView() === view
  }

  function _lsv2BasePath() {
    var path = String(window.location.pathname || '')
    var m = path.match(/^\/apps\/([^\/]+)\/([^\/]+)\/([^\/]+)(?:\/([^\/]+))?$/)
    if (m) return '/apps/' + m[1] + '/' + m[2] + '/lead-sources'

    m = path.match(/^\/([^\/]+)\/lead-sources(?:\/([^\/]+))?$/)
    if (m) return '/' + m[1] + '/lead-sources'

    return null
  }

  function _lsv2PathFor(view) {
    var base = _lsv2BasePath()
    if (!base) return window.location.pathname
    var safe = LS_V2_VIEWS.indexOf(view) >= 0 ? view : 'sources'
    return base + '/' + safe
  }

  function _lsv2Navigate(view, replace) {
    var target = _lsv2PathFor(view)
    if (replace) history.replaceState({}, '', target)
    else history.pushState({}, '', target)
    window._LS_ROUTE_VIEW = view
    if (typeof dispatch === 'function') dispatch()
  }

  async function _lsv2RefreshMetaForms(sourceId) {
    var id = Number(sourceId || 0)
    if (!id) return
    var btn = document.querySelector('[data-refresh-meta-forms="' + id + '"]')
    if (btn) btn.disabled = true
    try {
      var res = await authFetch('/api/lead-sources/' + id + '/meta/pull-recent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_history: false, per_form_limit: 25, page_size: 25, max_pages: 1 }),
      })
      var out = await _lsv2ReadJsonSafe(res)
      if (!res.ok) {
        if (typeof showToast === 'function') showToast(out.error || 'Failed to refresh forms', 'danger')
        return
      }
      if (typeof showToast === 'function') showToast('Meta source refreshed', 'success')
      _lsv2RenderSources()
      if (_lsv2ViewIs('forms')) _lsv2RenderForms()
    } finally {
      if (btn) btn.disabled = false
    }
  }

  function _lsv2CloseModal() {
    var el = document.getElementById('lsv2Modal')
    if (el) el.remove()
  }

  function _lsv2Modal(title, bodyHtml) {
    _lsv2CloseModal()
    var overlay = document.createElement('div')
    overlay.id = 'lsv2Modal'
    overlay.className = 'modal-overlay'
    overlay.innerHTML =
      '<div class="modal-box" style="max-width:820px;width:96%;max-height:90vh;overflow:auto;">' +
        '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px;">' +
          '<div><h3 class="sm-section-heading" style="margin:0;">' + _lsv2Esc(title) + '</h3></div>' +
          '<button class="lsv2-btn" onclick="_lsv2CloseModal()">Close</button>' +
        '</div>' +
        '<div id="lsv2ModalBody">' + bodyHtml + '</div>' +
      '</div>'
    overlay.addEventListener('click', function (evt) { if (evt.target === overlay) _lsv2CloseModal() })
    document.body.appendChild(overlay)
  }

  function _lsv2InfoRow(label, value) {
    return '<div style="padding:8px 0;border-bottom:1px solid #e5e7eb;">' +
      '<div class="lsv2-muted" style="font-size:11px;text-transform:uppercase;font-weight:800;">' + _lsv2Esc(label) + '</div>' +
      '<div style="font-weight:700;color:#0f172a;word-break:break-word;">' + _lsv2Esc(value || 'Not stored') + '</div>' +
    '</div>'
  }

  function _lsv2ChooseProjectApplyScope() {
    return new Promise(function (resolve) {
      var existing = document.getElementById('lsv2ProjectScopeModal')
      if (existing) existing.remove()
      var overlay = document.createElement('div')
      overlay.id = 'lsv2ProjectScopeModal'
      overlay.className = 'modal-overlay'
      overlay.innerHTML =
        '<div class="modal-box lsv2-scope-modal">' +
          '<div class="lsv2-scope-head">' +
            '<div>' +
              '<div class="lsv2-scope-eyebrow">Project mapping update</div>' +
              '<h3>Apply this project change to which leads?</h3>' +
              '<p>Choose whether this form mapping should affect only new incoming leads, or also update existing leads already connected to this form.</p>' +
            '</div>' +
            '<button class="lsv2-icon-btn" data-scope-cancel aria-label="Close">x</button>' +
          '</div>' +
          '<div class="lsv2-scope-options">' +
            '<button class="lsv2-scope-option" data-scope-value="future">' +
              '<span class="lsv2-scope-option-title">Future leads only</span>' +
              '<span class="lsv2-scope-option-copy">Save the mapping for leads received from now onward. Existing leads stay unchanged.</span>' +
            '</button>' +
            '<button class="lsv2-scope-option strong" data-scope-value="past_and_future">' +
              '<span class="lsv2-scope-option-title">Past and future leads</span>' +
              '<span class="lsv2-scope-option-copy">Save the mapping and update existing LMS leads that came from this form.</span>' +
            '</button>' +
          '</div>' +
          '<div class="lsv2-scope-foot">' +
            '<button class="lsv2-btn" data-scope-cancel>Cancel</button>' +
          '</div>' +
        '</div>'
      var done = function (value) {
        overlay.remove()
        resolve(value)
      }
      overlay.addEventListener('click', function (evt) {
        if (evt.target === overlay || evt.target.closest('[data-scope-cancel]')) done(null)
        var option = evt.target.closest('[data-scope-value]')
        if (option) done(String(option.getAttribute('data-scope-value') || 'future'))
      })
      document.body.appendChild(overlay)
    })
  }

  async function _lsv2ShowMetaConnectionInfo(sourceId) {
    var id = Number(sourceId || 0)
    if (!id) return
    _lsv2Modal('Meta Connection Info', '<div class="lsv2-muted">Loading connection info...</div>')
    var res = await authFetch('/api/lead-sources/' + id + '/meta/connection-info')
    var data = await _lsv2ReadJsonSafe(res)
    if (!res.ok) {
      var body = document.getElementById('lsv2ModalBody')
      if (body) body.innerHTML = '<div class="alert alert-danger">' + _lsv2Esc(data.error || 'Unable to load connection info') + '</div>'
      return
    }
    var biz = data.business || {}
    var page = data.page || {}
    var source = data.source || {}
    var accounts = data.ad_accounts || []
    var forms = data.forms || []
    var accountHtml = accounts.length
      ? accounts.map(function (a) {
          return '<div style="padding:6px 0;border-bottom:1px solid #eef2f7;"><strong>' + _lsv2Esc(a.name || 'Ad Account') + '</strong><br><span class="lsv2-muted">' + _lsv2Esc(a.id || '') + '</span></div>'
        }).join('')
      : '<div class="lsv2-muted">No ad account saved on this source.</div>'
    var formsHtml = forms.length
      ? forms.map(function (f) {
          return '<div style="padding:6px 0;border-bottom:1px solid #eef2f7;"><strong>' + _lsv2Esc(f.name || 'Unnamed form') + '</strong><br><span class="lsv2-muted">ID: ' + _lsv2Esc(f.id || '') + '</span></div>'
        }).join('')
      : '<div class="lsv2-muted">No forms saved on this source.</div>'
    var html =
      '<div class="lsv2-grid" style="grid-template-columns:repeat(auto-fit,minmax(250px,1fr));">' +
        '<div class="lsv2-card">' +
          _lsv2InfoRow('Source', source.name || '') +
          _lsv2InfoRow('Connected Page', page.name || source.connected_account || '') +
          _lsv2InfoRow('Page ID', page.id || '') +
          _lsv2InfoRow('Business ID', biz.id || '') +
          _lsv2InfoRow('Business Name', biz.name || '') +
          _lsv2InfoRow('Last Tested', source.last_tested_at || '') +
        '</div>' +
        '<div class="lsv2-card"><h4 style="margin:0 0 8px;">Ad Accounts</h4>' + accountHtml + '</div>' +
      '</div>' +
      '<div class="lsv2-card" style="margin-top:12px;"><h4 style="margin:0 0 8px;">Saved Forms (' + forms.length + ')</h4>' + formsHtml + '</div>' +
      (data.can_add_without_oauth ? '<div class="lsv2-actions" style="margin-top:12px;"><button class="lsv2-btn primary" onclick="_lsv2OpenMetaPageAdd(' + id + ')">Add Page Without OAuth</button></div>' : '<div class="alert alert-warning" style="margin-top:12px;">Stored user token is missing. Reconnect Meta once to enable adding pages without OAuth later.</div>')
    var body = document.getElementById('lsv2ModalBody')
    if (body) body.innerHTML = html
  }

  async function _lsv2OpenMetaPageAdd(sourceId) {
    var id = Number(sourceId || 0)
    if (!id) return
    _lsv2Modal('Add Meta Page', '<div class="lsv2-muted">Loading pages from saved Meta connection...</div>')
    var res = await authFetch('/api/lead-sources/' + id + '/meta/pages')
    var data = await _lsv2ReadJsonSafe(res)
    var body = document.getElementById('lsv2ModalBody')
    if (!res.ok) {
      if (body) body.innerHTML = '<div class="alert alert-danger">' + _lsv2Esc(data.error || 'Unable to load pages') + '</div>'
      return
    }
    var pages = data.pages || []
    var html = pages.length ? pages.map(function (p) {
      var badge = p.source_id ? '<span class="lsv2-badge ' + (p.is_active ? 'ok' : 'warn') + '">' + (p.is_active ? 'Already active' : 'Existing source') + '</span>' : ''
      return '<div class="lsv2-card" style="margin-bottom:10px;">' +
        '<div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start;">' +
          '<div><div style="font-weight:800;color:#0f172a;">' + _lsv2Esc(p.name || 'Meta Page') + '</div><div class="lsv2-muted">Page ID: ' + _lsv2Esc(p.id || '') + '</div></div>' +
          badge +
        '</div>' +
        '<div class="lsv2-actions"><button class="lsv2-btn primary" onclick="_lsv2LoadMetaPageForms(' + id + ',\'' + _lsv2Esc(p.id || '') + '\')">Choose Forms</button></div>' +
      '</div>'
    }).join('') : '<div class="lsv2-muted">No pages returned by Meta for the stored connection.</div>'
    if (body) body.innerHTML = html
  }

  async function _lsv2LoadMetaPageForms(sourceId, pageId) {
    var id = Number(sourceId || 0)
    pageId = String(pageId || '')
    var body = document.getElementById('lsv2ModalBody')
    if (body) body.innerHTML = '<div class="lsv2-muted">Loading forms...</div>'
    var res = await authFetch('/api/lead-sources/' + id + '/meta/pages/' + encodeURIComponent(pageId) + '/forms')
    var data = await _lsv2ReadJsonSafe(res)
    if (!res.ok) {
      if (body) body.innerHTML = '<div class="alert alert-danger">' + _lsv2Esc(data.error || 'Unable to load forms') + '</div>'
      return
    }
    var page = data.page || {}
    var forms = data.forms || []
    var formsHtml = forms.length ? forms.map(function (f, idx) {
      var safe = _lsv2Esc(f.id || '')
      return '<label style="display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-bottom:1px solid #eef2f7;cursor:pointer;">' +
        '<input type="checkbox" class="lsv2-meta-form-check" data-form-index="' + idx + '" checked>' +
        '<span><strong>' + _lsv2Esc(f.name || 'Unnamed form') + '</strong><br><span class="lsv2-muted">ID: ' + safe + (f.status ? ' | ' + _lsv2Esc(f.status) : '') + '</span></span>' +
      '</label>'
    }).join('') : '<div class="lsv2-muted">No lead forms returned for this page.</div>'
    window._lsv2PendingMetaForms = forms
    if (body) body.innerHTML =
      '<div class="lsv2-card">' +
        '<h4 style="margin:0 0 4px;">' + _lsv2Esc(page.name || 'Meta Page') + '</h4>' +
        '<div class="lsv2-muted" style="margin-bottom:10px;">Page ID: ' + _lsv2Esc(page.id || pageId) + '</div>' +
        formsHtml +
      '</div>' +
      '<div class="lsv2-actions" style="margin-top:12px;">' +
        '<button class="lsv2-btn" onclick="_lsv2OpenMetaPageAdd(' + id + ')">Back to Pages</button>' +
        '<button class="lsv2-btn primary" onclick="_lsv2SaveMetaPageForms(' + id + ',\'' + _lsv2Esc(page.id || pageId) + '\')">Save Page Forms</button>' +
      '</div>'
  }

  async function _lsv2SaveMetaPageForms(sourceId, pageId) {
    var forms = window._lsv2PendingMetaForms || []
    var selected = []
    document.querySelectorAll('.lsv2-meta-form-check').forEach(function (chk) {
      if (!chk.checked) return
      var idx = Number(chk.getAttribute('data-form-index') || -1)
      if (forms[idx]) selected.push(forms[idx])
    })
    if (!selected.length) {
      if (typeof showToast === 'function') showToast('Select at least one form.', 'warning')
      return
    }
    var res = await authFetch('/api/lead-sources/' + Number(sourceId || 0) + '/meta/pages/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ page_id: String(pageId || ''), selected_forms: selected }),
    })
    var data = await _lsv2ReadJsonSafe(res)
    if (!res.ok) {
      if (typeof showToast === 'function') showToast(data.error || 'Failed to save Meta page', 'danger')
      return
    }
    if (typeof showToast === 'function') showToast('Meta page saved. Map forms to projects next.', 'success')
    _lsv2CloseModal()
    _lsv2RenderSources()
    if (_lsv2ViewIs('forms')) _lsv2RenderForms()
  }

  function _lsv2NavHtml(active) {
    return LS_V2_VIEWS.map(function (view) {
      var label = view.charAt(0).toUpperCase() + view.slice(1)
      var cls = active === view ? 'lsv2-nav-item active' : 'lsv2-nav-item'
      return '<button class="' + cls + '" data-view="' + view + '">' + _lsv2Esc(label) + '</button>'
    }).join('')
  }

  function _lsv2InstallStyles() {
    if (document.getElementById('leadSourcesV2Styles')) return
    var style = document.createElement('style')
    style.id = 'leadSourcesV2Styles'
    style.textContent = [
      ':root{--lsv2-bg-a:#fffaf2;--lsv2-bg-b:#eff8ff;--lsv2-ink:#1f2937;--lsv2-soft:#6b7280;--lsv2-line:#e5e7eb;--lsv2-accent:#0f766e;--lsv2-accent-2:#0ea5e9;--lsv2-warn:#b45309;--lsv2-ok:#166534;}',
      '.lsv2-wrap{padding:22px;border-radius:18px;background:linear-gradient(140deg,var(--lsv2-bg-a),var(--lsv2-bg-b));border:1px solid #dbeafe;}',
      '.lsv2-top{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap;margin-bottom:16px}',
      '.lsv2-top h2{margin:0;color:var(--lsv2-ink);font-weight:800;letter-spacing:.2px}',
      '.lsv2-top p{margin:4px 0 0;color:var(--lsv2-soft)}',
      '.lsv2-nav{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 22px}',
      '.lsv2-nav-item{border:1px solid #cbd5e1;background:#ffffffb8;color:#334155;border-radius:999px;padding:8px 14px;font-size:12px;font-weight:700;cursor:pointer}',
      '.lsv2-nav-item.active{background:linear-gradient(135deg,var(--lsv2-accent),var(--lsv2-accent-2));color:#fff;border-color:transparent;box-shadow:0 8px 18px rgba(14,165,233,.22)}',
      '.lsv2-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}',
      '.lsv2-card{background:#fff;border:1px solid var(--lsv2-line);border-radius:14px;padding:14px;box-shadow:0 2px 6px rgba(2,6,23,.03)}',
      '.lsv2-sources-grid{grid-template-columns:repeat(auto-fill,minmax(340px,1fr));align-items:stretch}',
      '.lsv2-source-card{display:flex;flex-direction:column;min-width:0;min-height:250px;padding:16px}',
      '.lsv2-source-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:start;min-width:0}',
      '.lsv2-source-title-wrap{min-width:0;flex:1 1 auto}',
      '.lsv2-source-title{font-weight:850;color:#0f172a;line-height:1.28;font-size:15px;overflow-wrap:break-word}',
      '.lsv2-source-card .lsv2-badge{flex:0 0 auto;text-align:center;white-space:nowrap;line-height:1.1}',
      '.lsv2-source-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:14px}',
      '.lsv2-source-metrics div{border:1px solid #e2e8f0;background:#f8fafc;border-radius:10px;padding:8px;min-width:0}',
      '.lsv2-source-metrics span{display:block;color:#64748b;font-size:10px;font-weight:800;text-transform:uppercase;line-height:1.2}',
      '.lsv2-source-metrics strong{display:block;color:#0f172a;font-size:15px;font-weight:900;line-height:1.25;margin-top:4px;overflow-wrap:anywhere}',
      '.lsv2-source-card .lsv2-actions{margin-top:auto;padding-top:14px}',
      '.lsv2-source-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}',
      '.lsv2-source-card .lsv2-btn{padding:8px 11px;font-size:12px;min-height:36px}',
      '.lsv2-scope-modal{max-width:680px;width:94%;padding:0;overflow:hidden}',
      '.lsv2-scope-head{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;padding:22px 24px 16px;border-bottom:1px solid #e5e7eb;background:linear-gradient(180deg,#ffffff,#f8fafc)}',
      '.lsv2-scope-eyebrow{font-size:11px;font-weight:900;color:#0f766e;text-transform:uppercase;letter-spacing:.4px;margin-bottom:6px}',
      '.lsv2-scope-head h3{margin:0;color:#0f172a;font-size:20px;font-weight:900}',
      '.lsv2-scope-head p{margin:8px 0 0;color:#64748b;font-size:13px;line-height:1.45}',
      '.lsv2-icon-btn{border:1px solid #cbd5e1;background:#fff;color:#334155;border-radius:10px;width:34px;height:34px;font-size:16px;font-weight:900;cursor:pointer}',
      '.lsv2-scope-options{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;padding:18px 24px}',
      '.lsv2-scope-option{border:1px solid #dbe4ef;background:#fff;border-radius:12px;padding:16px;text-align:left;cursor:pointer;box-shadow:0 1px 2px rgba(15,23,42,.04)}',
      '.lsv2-scope-option:hover{border-color:#0f766e;box-shadow:0 10px 24px rgba(15,23,42,.08);transform:translateY(-1px)}',
      '.lsv2-scope-option.strong{border-color:#99f6e4;background:#f0fdfa}',
      '.lsv2-scope-option-title{display:block;color:#0f172a;font-weight:900;font-size:14px;margin-bottom:6px}',
      '.lsv2-scope-option-copy{display:block;color:#64748b;font-size:12px;line-height:1.45}',
      '.lsv2-scope-foot{display:flex;justify-content:flex-end;padding:0 24px 20px}',
      '.lsv2-kpi{font-size:26px;font-weight:900;color:#0f172a}',
      '.lsv2-kpi-strip{display:grid;grid-template-columns:repeat(5,minmax(140px,1fr));gap:10px;margin-bottom:8px}',
      '.lsv2-kpi-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin:0 0 10px}',
      '.lsv2-reports-global-controls{display:flex;align-items:center;justify-content:flex-end;gap:8px;flex:1 1 620px;min-width:0}',
      '.lsv2-reports-global-controls .lsv2-reports-date-shell{width:100%;min-width:0}',
      '.lsv2-kpi-title{margin:0;font-size:14px;font-weight:800;color:#1e293b;letter-spacing:.2px}',
      '.lsv2-kpi-card{background:linear-gradient(180deg,#ffffff,#f8fbff);border:1px solid #dbe6f4;border-radius:14px;padding:12px 12px 10px;box-shadow:0 2px 8px rgba(15,23,42,.05)}',
      '.lsv2-kpi-label{font-size:11px;font-weight:800;letter-spacing:.35px;text-transform:uppercase;color:#64748b}',
      '.lsv2-kpi-value{font-size:35px;font-weight:900;line-height:1.05;color:#000;margin-top:4px}',
      '.lsv2-kpi-value.ok{color:#000}',
      '.lsv2-kpi-value.warn{color:#000}',
      '.lsv2-kpi-value.err{color:#000}',
      '.lsv2-kpi-context{display:inline-flex;align-items:center;gap:6px;margin:0;padding:7px 10px;border-radius:999px;background:#eef6ff;border:1px solid #d4e6fb;color:#1e3a5f;font-size:12px;font-weight:800;white-space:nowrap}',
      '.lsv2-kpi-context.active{background:#dcfce7;border-color:#86efac;color:#166534}',
      '.lsv2-reports-date-shell{position:relative;display:block}',
      '.lsv2-reports-date-toolbar{display:grid;grid-template-columns:minmax(220px,1fr) auto;gap:12px;align-items:center}',
      '.lsv2-date-trigger{min-width:190px;max-width:100%;justify-content:space-between;display:inline-flex;align-items:center;gap:10px;height:38px;padding:0 12px;border-radius:10px;border:1px solid #cfd9e6;background:#fff;color:#111827;font-weight:800;box-shadow:0 1px 2px rgba(15,23,42,.04)}',
      '.lsv2-date-trigger:hover{border-color:#b9c7d8;box-shadow:0 6px 14px rgba(15,23,42,.08)}',
      '.lsv2-date-trigger span:first-child{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
      '.lsv2-date-picker-popover{display:none;position:fixed;z-index:1200;border:1px solid #d8e2ef;border-radius:12px;background:#fff;box-shadow:0 12px 26px rgba(15,23,42,.12);overflow:hidden;max-height:calc(100vh - 24px)}',
      '.lsv2-date-picker-popover.open{display:block}',
      '.lsv2-date-picker-layout{display:grid;grid-template-columns:160px minmax(0,1fr);min-height:0}',
      '.lsv2-date-picker-presets{padding:8px;background:#f8fafc;border-right:1px solid #e2e8f0;overflow:auto}',
      '.lsv2-date-picker-sidehead{margin:0 0 8px;color:#64748b;font-size:11px;font-weight:800;letter-spacing:.4px;text-transform:uppercase}',
      '.lsv2-date-picker-preset{width:100%;border:0;background:transparent;border-radius:8px;padding:7px 8px;font-size:12px;font-weight:700;color:#334155;text-align:left;cursor:pointer}',
      '.lsv2-date-picker-preset:hover{background:#e8f1ff;color:#1d4ed8}',
      '.lsv2-date-picker-preset.active{background:#dbeafe;color:#1d4ed8}',
      '.lsv2-date-picker-calendar-area{padding:10px 11px 11px;display:flex;flex-direction:column;gap:8px;min-width:0}',
      '.lsv2-date-picker-calendar-head{display:flex;align-items:center;justify-content:flex-start;gap:8px;padding:2px 0 1px}',
      '.lsv2-date-picker-calendars{display:flex;flex-direction:column;gap:10px;overflow-y:auto;max-height:340px;padding-right:2px;overscroll-behavior:contain}',
      '.lsv2-date-calendar-month{border:1px solid #e2e8f0;border-radius:11px;padding:8px;background:#fff;min-width:0;overflow:hidden;flex:0 0 auto;height:auto}',
      '.lsv2-date-calendar-month-title{font-size:11px;font-weight:800;color:#334155;margin-bottom:6px;text-align:center}',
      '.lsv2-date-calendar-weekdays,.lsv2-date-calendar-grid{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:3px}',
      '.lsv2-date-calendar-weekdays span{font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:.2px;color:#94a3b8;text-align:center;padding:1px 0;white-space:nowrap;overflow:hidden;text-overflow:clip}',
      '.lsv2-date-calendar-pad{height:28px}',
      '.lsv2-date-calendar-day{height:28px;width:100%;min-width:0;padding:0;border:0;border-radius:999px;background:transparent;color:#1f2937;font-size:11px;font-weight:700;line-height:1;display:flex;align-items:center;justify-content:center;cursor:pointer}',
      '.lsv2-date-calendar-day:hover{background:#e8f1ff;color:#1d4ed8}',
      '.lsv2-date-calendar-day.disabled,.lsv2-date-calendar-day:disabled{background:#f8fafc;color:#94a3b8;cursor:not-allowed;opacity:.9}',
      '.lsv2-date-calendar-day.disabled:hover,.lsv2-date-calendar-day:disabled:hover{background:#f8fafc;color:#94a3b8}',
      '.lsv2-date-calendar-day.today{box-shadow:inset 0 0 0 1px #cbd5e1}',
      '.lsv2-date-calendar-day.in-range{background:#e0f2fe;border-radius:8px}',
      '.lsv2-date-calendar-day.start,.lsv2-date-calendar-day.end{background:#0f766e;color:#fff}',
      '.lsv2-date-picker-actions{display:flex;justify-content:flex-end;align-items:center;gap:8px;flex-wrap:wrap;border-top:1px solid #e2e8f0;padding-top:10px;margin-top:4px}',
      '.lsv2-date-picker-actions .lsv2-btn{min-width:72px}',
      '.lsv2-muted{font-size:12px;color:#6b7280}',
      '.lsv2-table-wrap{overflow:auto;background:#fff;border:1px solid var(--lsv2-line);border-radius:14px}',
      '.lsv2-table{width:100%;border-collapse:collapse;font-size:13px}',
      '.lsv2-table th,.lsv2-table td{padding:10px 12px;border-bottom:1px solid #eef2f7;white-space:nowrap;text-align:center}',
      '.lsv2-table th{background:#f8fafc;text-transform:uppercase;font-size:11px;letter-spacing:.35px;color:#475569}',
      '.lsv2-toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;margin-bottom:12px;padding:12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px}',
      '.lsv2-toolbar .form-label{font-size:12px;font-weight:700;margin-bottom:4px}',
      '.lsv2-toggle{display:flex;gap:8px;align-items:center;font-size:12px;font-weight:700;color:#334155}',
      '.lsv2-toggle input{width:16px;height:16px}',
      '.lsv2-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}',
      '.lsv2-btn{border:1px solid #cbd5e1;background:#fff;border-radius:10px;padding:8px 12px;font-size:12px;font-weight:700;cursor:pointer}',
      '.lsv2-btn:hover{transform:translateY(-1px);box-shadow:0 6px 14px rgba(15,23,42,.08)}',
      '.lsv2-btn:disabled{opacity:.55;cursor:not-allowed;transform:none;box-shadow:none}',
      '.lsv2-btn.primary{background:#0f766e;color:#fff;border-color:#0f766e}',
      '.lsv2-btn.sky{background:#0ea5e9;color:#fff;border-color:#0ea5e9}',
      '.lsv2-btn.subtle{background:#f8fafc;border-color:#dbe4ef;color:#334155}',
      '.lsv2-input-compact{height:36px;border-radius:10px;width:100%}',
      '.lsv2-logs-filter-card{margin-bottom:12px;padding:14px 14px 12px}',
      '.lsv2-logs-filter-grid{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}',
      '.lsv2-logs-field{display:flex;flex-direction:column;gap:6px}',
      '.lsv2-logs-field .form-label{margin:0;font-size:12px;font-weight:700;line-height:1.1}',
      '.lsv2-logs-filter-grid .field-wide{flex:2 1 300px;min-width:240px}',
      '.lsv2-logs-filter-grid .field-mid{flex:1 1 155px;min-width:140px}',
      '.lsv2-logs-filter-toggle{display:flex;align-items:center;gap:8px;margin:0 2px 8px 0;font-size:12px;font-weight:700;color:#334155;white-space:nowrap}',
      '.lsv2-logs-filter-actions{display:flex;gap:6px;align-items:flex-end}',
      '.lsv2-logs-actions{margin:12px 0 10px;padding:12px;background:#fff;position:static;top:auto;z-index:auto;backdrop-filter:none}',
      '.lsv2-logs-actions-inner{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap}',
      '.lsv2-logs-bulk{display:flex;gap:8px;align-items:center;flex-wrap:wrap}',
      '.lsv2-logs-download{margin-left:auto}',
      '.lsv2-logs-pagination{display:flex;gap:8px;align-items:center;justify-content:space-between;margin:10px 0;font-size:12px;flex-wrap:wrap;background:rgba(255,255,255,.94);border:1px solid #e2e8f0;border-radius:12px;padding:8px 10px;position:sticky;bottom:8px;z-index:5;backdrop-filter:saturate(130%) blur(2px)}',
      '.lsv2-logs-pagination-left,.lsv2-logs-pagination-right{display:flex;gap:8px;align-items:center;flex-wrap:wrap}',
      '.lsv2-table-wrap.logs{border-radius:12px}',
      '.lsv2-reports-filter-card{margin:12px 0 10px;padding:14px 14px 12px}',
      '.lsv2-reports-filter-grid{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end}',
      '.lsv2-reports-filter-actions{display:flex;gap:6px;align-items:flex-end}',
      '.lsv2-reports-actions{margin:0 0 10px;padding:10px 12px;background:#fff}',
      '.lsv2-reports-actions-inner{display:flex;gap:10px;align-items:center;justify-content:space-between;flex-wrap:wrap}',
      '.lsv2-reports-pagination{display:flex;gap:8px;align-items:center;justify-content:space-between;margin:10px 0;font-size:12px;flex-wrap:wrap;background:rgba(255,255,255,.94);border:1px solid #e2e8f0;border-radius:12px;padding:8px 10px}',
      '.lsv2-reports-pagination-left,.lsv2-reports-pagination-right{display:flex;gap:8px;align-items:center;flex-wrap:wrap}',
      '.lsv2-reports-pagination .lsv2-btn.page{padding:7px 10px;min-width:34px}',
      '.lsv2-badge{display:inline-block;padding:4px 8px;border-radius:999px;font-size:11px;font-weight:800}',
      '.lsv2-badge.ok{background:#dcfce7;color:#166534}',
      '.lsv2-badge.warn{background:#fef3c7;color:#92400e}',
      '.lsv2-badge.err{background:#fee2e2;color:#991b1b}',
      '.lsv2-checklist{margin:10px 0 0;padding:0;list-style:none}',
      '.lsv2-checklist li{padding:6px 0;border-top:1px solid #eef2f7;text-align:left}',
      '.lsv2-checklist li:first-child{border-top:0}',
      '@media (max-width:1100px){.lsv2-kpi-strip{grid-template-columns:repeat(3,minmax(140px,1fr))}}',
      '@media (max-width:768px){.lsv2-wrap{padding:14px}.lsv2-top h2{font-size:22px}.lsv2-sources-grid{grid-template-columns:1fr}.lsv2-source-card{min-height:0}.lsv2-scope-options{grid-template-columns:1fr;padding:14px}.lsv2-scope-head{padding:18px 16px 14px}.lsv2-scope-foot{padding:0 14px 16px}.lsv2-kpi-strip{grid-template-columns:repeat(2,minmax(130px,1fr))}.lsv2-kpi-value{font-size:30px}.lsv2-kpi-head{margin-bottom:8px}.lsv2-kpi-context{font-size:11px;padding:6px 9px}.lsv2-reports-global-controls{flex-basis:100%;justify-content:stretch}.lsv2-reports-date-toolbar{grid-template-columns:1fr}.lsv2-date-trigger{width:100%;min-width:0}.lsv2-date-picker-layout{grid-template-columns:1fr}.lsv2-date-picker-presets{border-right:0;border-bottom:1px solid #e2e8f0}.lsv2-date-picker-calendars{max-height:300px}.lsv2-logs-filter-grid .field-wide,.lsv2-logs-filter-grid .field-mid{min-width:100%}.lsv2-logs-filter-actions{width:100%}.lsv2-logs-filter-actions .lsv2-btn{flex:1}.lsv2-logs-download{margin-left:0}.lsv2-logs-pagination{bottom:4px}.lsv2-reports-filter-grid .field-wide,.lsv2-reports-filter-grid .field-mid{min-width:100%}.lsv2-reports-filter-actions{width:100%}.lsv2-reports-filter-actions .lsv2-btn{flex:1}}'
    ].join('')
    document.head.appendChild(style)
  }

  function _lsv2BindNav() {
    var nav = document.getElementById('lsv2-nav')
    if (!nav) return
    nav.querySelectorAll('[data-view]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        _lsv2Navigate(String(btn.getAttribute('data-view') || 'sources'))
      })
    })
  }

  function _lsv2SetBody(html) {
    var el = document.getElementById('lsv2-body')
    if (el) el.innerHTML = html
  }

  async function _lsv2RenderSources() {
    if (!_lsv2ViewIs('sources')) return
    _lsv2SetBody('<div class="lsv2-muted">Loading connected sources...</div>')
    var res = await authFetch('/api/lead-sources?include_inactive=true')
    if (!_lsv2ViewIs('sources')) return
    var data = await _lsv2ReadJsonSafe(res)
    if (!_lsv2ViewIs('sources')) return
    if (!res.ok) {
      _lsv2SetBody('<div class="alert alert-danger">' + _lsv2Esc(data.error || 'Unable to load sources') + '</div>')
      return
    }

    var items = data.sources || []
    if (!items.length) {
      _lsv2SetBody(
        '<div class="lsv2-card">' +
          '<h4>No lead source configured</h4>' +
          '<p class="lsv2-muted">Connect Meta/Google or add webhook sources to start ingestion.</p>' +
          '<div class="lsv2-actions"><button class="lsv2-btn primary" onclick="_lsv2Navigate(\'connect\')">Connect Source</button></div>' +
        '</div>'
      )
      return
    }

    var cards = items.map(function (s) {
      var gate = (s.mapping_gate || {})
      var formCount = (s.available_forms || []).length
      var tone = gate.required && !gate.is_ready ? 'warn' : (s.is_active ? 'ok' : 'err')
      var status = gate.required && !gate.is_ready ? 'Mapping pending' : (s.is_active ? 'Active' : 'Inactive')
      var isMeta = String(s.source_type || '') === 'meta'
      var submissions = Number(s.ingestion_events_count || s.total_leads_ingested || 0)
      var lmsLeads = Number(s.lms_leads_count || 0)
      return '<div class="lsv2-card lsv2-source-card">' +
        '<div class="lsv2-source-head">' +
          '<div class="lsv2-source-title-wrap"><div class="lsv2-source-title">' + _lsv2Esc(s.name || 'Untitled Source') + '</div><div class="lsv2-muted">' + _lsv2Esc(s.source_type || 'source') + '</div></div>' +
          '<span class="lsv2-badge ' + tone + '">' + status + '</span>' +
        '</div>' +
        '<div class="lsv2-source-metrics">' +
          '<div><span>Forms</span><strong>' + formCount + '</strong></div>' +
          '<div><span>Submissions</span><strong>' + submissions.toLocaleString() + '</strong></div>' +
          '<div><span>LMS leads</span><strong>' + lmsLeads.toLocaleString() + '</strong></div>' +
        '</div>' +
        '<div class="lsv2-actions lsv2-source-actions">' +
          '<button class="lsv2-btn" onclick="_lsv2GoMappings(' + Number(s.id || 0) + ')">Map Forms</button>' +
          (isMeta ? '<button class="lsv2-btn" data-refresh-meta-forms="' + Number(s.id || 0) + '" onclick="_lsv2RefreshMetaForms(' + Number(s.id || 0) + ')">Refresh Forms</button>' : '') +
          (isMeta ? '<button class="lsv2-btn" onclick="_lsv2ShowMetaConnectionInfo(' + Number(s.id || 0) + ')">Details</button>' : '') +
          (isMeta ? '<button class="lsv2-btn" onclick="_lsv2OpenMetaPageAdd(' + Number(s.id || 0) + ')">Add Page</button>' : '') +
          '<button class="lsv2-btn" onclick="_lsv2TestSource(' + Number(s.id || 0) + ')">Test</button>' +
          '<button class="lsv2-btn ' + (s.is_active ? '' : 'primary') + '" onclick="_lsv2ToggleSource(' + Number(s.id || 0) + ',' + (!s.is_active) + ')">' + (s.is_active ? 'Disable' : 'Enable') + '</button>' +
          (s.is_active ? '' : '<button class="lsv2-btn" style="color:#dc2626;border-color:#dc2626" onclick="_lsv2DeleteSource(' + Number(s.id || 0) + ',\'' + _lsv2Esc(s.name || 'Source') + '\')">Delete</button>') +
        '</div>' +
      '</div>'
    }).join('')

    _lsv2SetBody('<div class="lsv2-grid lsv2-sources-grid">' + cards + '</div>')
  }

  async function _lsv2RenderConnect() {
    if (!_lsv2ViewIs('connect')) return
    _lsv2SetBody('<div class="lsv2-muted">Loading connection tools...</div>')
    if (typeof window.ensureLegacyLeadSourcesLoaded === 'function') {
      try { await window.ensureLegacyLeadSourcesLoaded() } catch (_e) {}
    }
    if (!_lsv2ViewIs('connect')) return
    var urlParams = new URLSearchParams(window.location.search)
    var googleSession = urlParams.get('google_session')
    var metaSession = urlParams.get('meta_session')
    var persistedGoogleWizard = (typeof _lsLoadPersistedGoogleWizard === 'function') ? _lsLoadPersistedGoogleWizard() : null
    var persistedMetaWizard = (typeof _lsLoadPersistedMetaWizard === 'function') ? _lsLoadPersistedMetaWizard() : null

    function _lsv2LaunchExternalWizard(kind) {
      var fn = kind === 'google' ? window._lsStartGoogleWizard || window._lsStartGoogleWizard : window._lsStartMetaWizard || window._lsStartMetaWizard
      if (typeof fn === 'function') {
        fn()
        return true
      }
      return false
    }

    function _lsv2LaunchWithRetry(kind) {
      if (_lsv2LaunchExternalWizard(kind)) return
      setTimeout(function () {
        if (_lsv2LaunchExternalWizard(kind)) return
        var wizardEl = document.getElementById('ls-wizard-area')
        if (!wizardEl) return
        var label = kind === 'google' ? 'Google' : 'Meta'
        wizardEl.innerHTML =
          '<div class="alert alert-warning">' +
          label + ' wizard could not be initialized automatically. ' +
          'Please click <strong>Start ' + label + ' Wizard</strong> once.</div>'
      }, 150)
    }

    _lsv2SetBody(
      '<div class="lsv2-grid">' +
        '<div class="lsv2-card"><h4>Meta Connection</h4><p class="lsv2-muted">OAuth flow, page selection, and form sync.</p><div class="lsv2-actions"><button class="lsv2-btn primary" onclick="_lsStartMetaWizard()">Start Meta Wizard</button></div></div>' +
        '<div class="lsv2-card"><h4>Google Connection</h4><p class="lsv2-muted">OAuth setup for Google lead forms.</p><div class="lsv2-actions"><button class="lsv2-btn sky" onclick="_lsStartGoogleWizard()">Start Google Wizard</button></div></div>' +
        '<div class="lsv2-card"><h4>Manual / Webhook</h4><p class="lsv2-muted">Custom channels with webhook token and rules.</p><div class="lsv2-actions"><button class="lsv2-btn" onclick="_lsRenderForm(null)">Open Manual Form</button></div></div>' +
      '</div>' +
      '<div id="ls-wizard-area" style="margin-top:16px"></div>'
    )

    if (!_lsv2ViewIs('connect')) return

    if (googleSession) {
      _lsv2LaunchWithRetry('google')
      return
    }
    if (metaSession) {
      _lsv2LaunchWithRetry('meta')
      return
    }
    if (persistedGoogleWizard && persistedGoogleWizard.step >= 2) {
      _lsv2LaunchWithRetry('google')
      return
    }
    if (persistedMetaWizard && persistedMetaWizard.step >= 3) {
      _lsv2LaunchWithRetry('meta')
      return
    }
  }

  async function _lsv2RenderForms() {
    if (!_lsv2ViewIs('forms')) return
    _lsv2SetBody('<div class="lsv2-muted">Loading form mappings...</div>')
    var sourcesRes = await authFetch('/api/lead-sources')
    if (!_lsv2ViewIs('forms')) return
    var sourcesData = await _lsv2ReadJsonSafe(sourcesRes)
    if (!_lsv2ViewIs('forms')) return
    if (!sourcesRes.ok) {
      _lsv2SetBody('<div class="alert alert-danger">' + _lsv2Esc(sourcesData.error || 'Unable to load sources') + '</div>')
      return
    }

    var sources = (sourcesData.sources || []).filter(function (s) { return s.source_type === 'meta' || s.source_type === 'google' })
    if (!sources.length) {
      _lsv2SetBody('<div class="lsv2-card"><h4>No source eligible for mapping</h4><p class="lsv2-muted">Connect Meta/Google first.</p></div>')
      return
    }

    var selectedId = Number(window._LS_V2_SELECTED_SOURCE_ID || sources[0].id)
    if (!sources.some(function (s) { return Number(s.id) === selectedId })) selectedId = Number(sources[0].id)
    window._LS_V2_SELECTED_SOURCE_ID = selectedId

    var projectsRes = await authFetch('/api/projects')
    if (!_lsv2ViewIs('forms')) return
    var projectsData = await _lsv2ReadJsonSafe(projectsRes)
    if (!_lsv2ViewIs('forms')) return
    var projects = projectsRes.ok ? (projectsData.projects || []) : []

    var managersRes = await authFetch('/api/users')
    if (!_lsv2ViewIs('forms')) return
    var managersData = await _lsv2ReadJsonSafe(managersRes)
    if (!_lsv2ViewIs('forms')) return
    var managers = managersRes.ok
      ? (managersData.users || []).filter(function (u) { return u && u.role === 'sales_manager' && u.is_active !== false })
      : []

    var mappingRes = await authFetch('/api/lead-sources/' + selectedId + '/forms/mappings')
    if (!_lsv2ViewIs('forms')) return
    var mappingData = await _lsv2ReadJsonSafe(mappingRes)
    if (!_lsv2ViewIs('forms')) return
    if (!mappingRes.ok) {
      _lsv2SetBody('<div class="alert alert-danger">' + _lsv2Esc(mappingData.error || 'Unable to load mappings') + '</div>')
      return
    }

    var forms = (mappingData.summary && mappingData.summary.forms) || []
    var rows = mappingData.rows || []
    var rowByForm = {}
    rows.forEach(function (r) { rowByForm[String(r.form_id)] = r })

    var sourceOptions = sources.map(function (s) {
      var selected = Number(s.id) === selectedId ? 'selected' : ''
      return '<option value="' + Number(s.id) + '" ' + selected + '>' + _lsv2Esc(s.name) + '</option>'
    }).join('')

    var projectOptionsHtml = function (projectId) {
      var options = ['<option value="">Select project</option>']
      projects.forEach(function (p) {
        var selected = Number(p.id) === Number(projectId) ? 'selected' : ''
        options.push('<option value="' + Number(p.id) + '" ' + selected + '>' + _lsv2Esc(p.name) + '</option>')
      })
      return options.join('')
    }

    var managerOptionsHtml = function (managerId) {
      var options = ['<option value="">Select manager</option>']
      managers.forEach(function (m) {
        var selected = Number(m.id) === Number(managerId) ? 'selected' : ''
        options.push('<option value="' + Number(m.id) + '" ' + selected + '>' + _lsv2Esc(m.name) + '</option>')
      })
      return options.join('')
    }

    var modeOptionsHtml = function (mode) {
      var m = String(mode || 'none')
      var options = [
        { value: 'none', label: 'None' },
        { value: 'fixed_manager', label: 'Fixed Manager' },
        { value: 'round_robin_pool', label: 'Round Robin Pool' },
      ]
      return options.map(function (opt) {
        var selected = opt.value === m ? 'selected' : ''
        return '<option value="' + opt.value + '" ' + selected + '>' + _lsv2Esc(opt.label) + '</option>'
      }).join('')
    }

    var bodyRows = forms.map(function (f) {
      var existing = rowByForm[String(f.id)] || {}
      var mode = String(existing.manager_assign_mode || 'none')
      var rrPoolCsv = (existing.rr_manager_pool || []).join(', ')
      return '<tr>' +
        '<td>' + _lsv2Esc(f.name || '-') + '<div class="lsv2-muted">' + _lsv2Esc(f.id) + '</div></td>' +
        '<td><select class="form-select form-select-sm" data-form-id="' + _lsv2Esc(f.id) + '">' + projectOptionsHtml(existing.project_id) + '</select></td>' +
        '<td><select class="form-select form-select-sm" data-manager-mode-for="' + _lsv2Esc(f.id) + '">' + modeOptionsHtml(mode) + '</select></td>' +
        '<td>' +
          '<div data-fixed-wrap-for="' + _lsv2Esc(f.id) + '" style="display:' + (mode === 'fixed_manager' ? 'block' : 'none') + '">' +
            '<select class="form-select form-select-sm" data-fixed-manager-for="' + _lsv2Esc(f.id) + '">' + managerOptionsHtml(existing.manager_id) + '</select>' +
          '</div>' +
          '<div data-rr-wrap-for="' + _lsv2Esc(f.id) + '" style="display:' + (mode === 'round_robin_pool' ? 'block' : 'none') + '">' +
            '<input class="form-control form-control-sm" data-rr-pool-for="' + _lsv2Esc(f.id) + '" placeholder="Manager IDs: 2,3,20" value="' + _lsv2Esc(rrPoolCsv) + '" />' +
            '<div class="lsv2-muted" style="margin-top:4px">Enter manager IDs separated by commas.</div>' +
          '</div>' +
          '<div data-none-wrap-for="' + _lsv2Esc(f.id) + '" class="lsv2-muted" style="display:' + (mode === 'none' ? 'block' : 'none') + '">No pre-assignment</div>' +
        '</td>' +
      '</tr>'
    }).join('')

    _lsv2SetBody(
      '<div class="lsv2-card" style="margin-bottom:12px">' +
        '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:space-between">' +
          '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">' +
          '<label style="font-weight:700">Source</label>' +
          '<select id="lsv2-source-select" class="form-select form-select-sm" style="width:auto;min-width:240px">' + sourceOptions + '</select>' +
          '<span class="lsv2-badge ' + (((mappingData.summary || {}).is_ready) ? 'ok' : 'warn') + '">' + (((mappingData.summary || {}).is_ready) ? 'Activation ready' : 'Mapping required') + '</span>' +
          '</div>' +
          '<div class="lsv2-actions" style="margin-top:0"><button id="lsv2-refresh-forms" class="lsv2-btn">Refresh forms</button></div>' +
        '</div>' +
      '</div>' +
      '<div class="lsv2-table-wrap"><table class="lsv2-table"><thead><tr><th>Lead Form</th><th>Mapped Project</th><th>Manager Rule</th><th>Manager Config</th></tr></thead><tbody>' + bodyRows + '</tbody></table></div>' +
      '<div class="lsv2-actions"><button id="lsv2-save-map" class="lsv2-btn primary">Save mappings</button></div>'
    )

    document.querySelectorAll('[data-manager-mode-for]').forEach(function (modeSel) {
      modeSel.addEventListener('change', function () {
        var formId = String(modeSel.getAttribute('data-manager-mode-for') || '')
        var mode = String(modeSel.value || 'none')
        var fixedWrap = document.querySelector('[data-fixed-wrap-for="' + formId + '"]')
        var rrWrap = document.querySelector('[data-rr-wrap-for="' + formId + '"]')
        var noneWrap = document.querySelector('[data-none-wrap-for="' + formId + '"]')
        if (fixedWrap) fixedWrap.style.display = mode === 'fixed_manager' ? 'block' : 'none'
        if (rrWrap) rrWrap.style.display = mode === 'round_robin_pool' ? 'block' : 'none'
        if (noneWrap) noneWrap.style.display = mode === 'none' ? 'block' : 'none'
      })
    })

    var sourceSelect = document.getElementById('lsv2-source-select')
    if (sourceSelect) {
      sourceSelect.addEventListener('change', function () {
        window._LS_V2_SELECTED_SOURCE_ID = Number(sourceSelect.value)
        _lsv2RenderForms()
      })
    }

    var saveBtn = document.getElementById('lsv2-save-map')
    if (saveBtn) {
      saveBtn.addEventListener('click', async function () {
        var payload = []
        var hasProjectChanges = false
        document.querySelectorAll('[data-form-id]').forEach(function (sel) {
          var formId = String(sel.getAttribute('data-form-id') || '')
          var projectId = Number(sel.value || 0)
          if (!formId || !projectId) return
          var existingRow = rowByForm[String(formId)] || {}
          if (Number(existingRow.project_id || 0) !== projectId) hasProjectChanges = true

          var modeSel = document.querySelector('[data-manager-mode-for="' + formId + '"]')
          var mode = String((modeSel && modeSel.value) || 'none')
          var row = { form_id: formId, project_id: projectId, manager_assign_mode: mode }

          if (mode === 'fixed_manager') {
            var fixedSel = document.querySelector('[data-fixed-manager-for="' + formId + '"]')
            var managerId = Number((fixedSel && fixedSel.value) || 0)
            if (managerId) row.manager_id = managerId
          } else if (mode === 'round_robin_pool') {
            var rrInput = document.querySelector('[data-rr-pool-for="' + formId + '"]')
            var rrRaw = String((rrInput && rrInput.value) || '')
            row.rr_manager_pool = rrRaw
              .split(',')
              .map(function (x) { return parseInt(String(x || '').trim(), 10) })
              .filter(function (x) { return Number.isFinite(x) && x > 0 })
          }

          payload.push(row)
        })

        var applyScope = 'future'
        if (hasProjectChanges) {
          var selectedScope = await _lsv2ChooseProjectApplyScope()
          if (!selectedScope) return
          applyScope = selectedScope
        }

        saveBtn.disabled = true
        var res = await authFetch('/api/lead-sources/' + selectedId + '/forms/mappings', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ rows: payload, apply_scope: applyScope }),
        })
        saveBtn.disabled = false
        var out = await _lsv2ReadJsonSafe(res)
        if (!res.ok) {
          if (typeof showToast === 'function') showToast(out.error || 'Failed to save mappings', 'danger')
          return
        }
        var updatedCount = Number(out.updated_existing_leads || 0)
        var message = applyScope === 'past_and_future'
          ? 'Form mappings saved. Updated ' + updatedCount + ' existing leads.'
          : 'Form mappings saved for future leads.'
        if (typeof showToast === 'function') showToast(message, 'success')
        _lsv2RenderForms()
      })
    }

    var refreshFormsBtn = document.getElementById('lsv2-refresh-forms')
    if (refreshFormsBtn) {
      refreshFormsBtn.addEventListener('click', function () {
        _lsv2RenderForms()
      })
    }
  }

  async function _lsv2RenderValidation() {
    if (!_lsv2ViewIs('validation')) return
    _lsv2SetBody('<div class="lsv2-muted">Loading validation runner...</div>')
    var res = await authFetch('/api/lead-sources')
    if (!_lsv2ViewIs('validation')) return
    var data = await _lsv2ReadJsonSafe(res)
    if (!_lsv2ViewIs('validation')) return
    if (!res.ok) {
      _lsv2SetBody('<div class="alert alert-danger">' + _lsv2Esc(data.error || 'Unable to load sources') + '</div>')
      return
    }

    var sources = data.sources || []
    var metaSources = sources.filter(function (s) { return s.source_type === 'meta' })
    var googleSources = sources.filter(function (s) { return s.source_type === 'google' })
    var metaOptions = metaSources.map(function (s) {
      return '<option value="' + Number(s.id) + '">' + _lsv2Esc(s.name) + '</option>'
    }).join('')
    var googleOptions = googleSources.map(function (s) {
      return '<option value="' + Number(s.id) + '">' + _lsv2Esc(s.name) + '</option>'
    }).join('')

    _lsv2SetBody(
      '<div class="lsv2-card">' +
        '<h4>Validation Center</h4>' +
        '<p class="lsv2-muted">Pick a source and run only the checks that belong to that platform.</p>' +
        '<div class="row g-2" style="max-width:780px">' +
          '<div class="col-md-6"><label class="form-label">Meta source</label><select id="lsv2-val-meta" class="form-select form-select-sm"><option value="">Select</option>' + metaOptions + '</select></div>' +
          '<div class="col-md-6"><label class="form-label">Google source</label><select id="lsv2-val-google" class="form-select form-select-sm"><option value="">Select</option>' + googleOptions + '</select></div>' +
        '</div>' +
        '<div class="lsv2-actions"><button id="lsv2-run-validation" class="lsv2-btn primary">Run validation</button></div>' +
        '<div id="lsv2-validation-out" style="margin-top:8px"></div>' +
      '</div>'
    )

    var runBtn = document.getElementById('lsv2-run-validation')
    if (runBtn) {
      runBtn.addEventListener('click', async function () {
        var metaId = Number((document.getElementById('lsv2-val-meta') || {}).value || 0)
        var googleId = Number((document.getElementById('lsv2-val-google') || {}).value || 0)
        runBtn.disabled = true
        var r = await authFetch('/api/lead-sources/validate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ meta_source_id: metaId || null, google_source_id: googleId || null }),
        })
        runBtn.disabled = false
        var out = await _lsv2ReadJsonSafe(r)
        var host = document.getElementById('lsv2-validation-out')
        if (!host) return
        if (!r.ok) {
          host.innerHTML = '<div class="alert alert-danger">' + _lsv2Esc(out.error || 'Validation failed') + '</div>'
          return
        }
        var info = _lsv2ValidationInfo()
        var items = out.items || {}
        var keys = []
        if (metaId) {
          keys.push('meta_connection', 'meta_lead_validation')
        }
        if (googleId) {
          keys.push('google_connection', 'google_lead_validation')
        }
        if (!keys.length) {
          host.innerHTML = '<div class="alert alert-warning">Select a Meta source, a Google source, or both before running validation.</div>'
          return
        }
        var html = keys.map(function (k) {
          var it = items[k] || {}
          var tone = it.passed ? 'ok' : 'err'
          var meta = info[k] || { title: it.label || k, why: '', fix: '' }
          var sub = it.sub || {}
          var subKeys = Object.keys(sub)
          var subHtml = subKeys.length ? '<ul class="lsv2-checklist">' + subKeys.map(function (sk) {
            return '<li><strong>' + _lsv2Esc(sk.replace(/_/g, ' ')) + '</strong>: ' + _lsv2Esc(sub[sk] ? 'Yes' : 'No') + '</li>'
          }).join('') + '</ul>' : ''
          return '<div class="lsv2-card" style="margin-top:12px">' +
            '<div style="display:flex;justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap">' +
              '<div><div style="font-weight:800;color:#0f172a">' + _lsv2Esc(meta.title) + '</div><div class="lsv2-muted">' + _lsv2Esc(meta.why) + '</div></div>' +
              '<span class="lsv2-badge ' + tone + '">' + _lsv2Esc(it.result || '-') + '</span>' +
            '</div>' +
            '<div style="margin-top:10px"><div><strong>Checked:</strong> ' + _lsv2Esc(it.detail || 'No detail returned') + '</div><div style="margin-top:4px"><strong>Why it matters:</strong> ' + _lsv2Esc(meta.why) + '</div><div style="margin-top:4px"><strong>If failed:</strong> ' + _lsv2Esc(meta.fix) + '</div></div>' +
            subHtml +
          '</div>'
        }).join('')
        host.innerHTML = html || '<span class="lsv2-muted">No validation items returned.</span>'
      })
    }
  }

  async function _lsv2RenderLogs() {
    if (!_lsv2ViewIs('logs')) return
    _lsv2SetBody('<div class="lsv2-muted">Loading source leads...</div>')
    var page = Number(window._LS_V2_LOGS_PAGE || 1)
    var perPage = Number(window._LS_V2_LOGS_PER_PAGE || 25)
    if (!Number.isFinite(perPage) || perPage < 10) perPage = 25
    var searchQ = String(window._LS_V2_LOGS_Q || '').trim()
    var statusFilter = String(window._LS_V2_LOGS_STATUS || '').trim()
    var dateFrom = String(window._LS_V2_LOGS_DATE_FROM || '').trim()
    var dateTo = String(window._LS_V2_LOGS_DATE_TO || '').trim()
    var showTestData = _lsv2ShowTestDataEnabled()
    
    var params = new URLSearchParams()
    params.append('page', page)
    params.append('per_page', perPage)
    if (searchQ) params.append('q', searchQ)
    if (statusFilter) params.append('status', statusFilter)
    if (dateFrom) params.append('date_from', dateFrom)
    if (dateTo) params.append('date_to', dateTo)
    _lsv2ApplyTestDataParam(params)

    var exportParams = new URLSearchParams()
    if (searchQ) exportParams.append('q', searchQ)
    if (statusFilter) exportParams.append('status', statusFilter)
    if (dateFrom) exportParams.append('date_from', dateFrom)
    if (dateTo) exportParams.append('date_to', dateTo)
    _lsv2ApplyTestDataParam(exportParams)
    var exportQuery = exportParams.toString()
    var csvHref = _lsv2ApiHref('/api/lead-sources/logs/export.csv' + (exportQuery ? ('?' + exportQuery) : ''))
    
    var res = await authFetch('/api/lead-sources/logs?' + params.toString())
    if (!_lsv2ViewIs('logs')) return
    var data = await _lsv2ReadJsonSafe(res)
    if (!_lsv2ViewIs('logs')) return
    if (!res.ok) {
      _lsv2SetBody('<div class="alert alert-danger">' + _lsv2Esc(data.error || 'Unable to load logs') + '</div>')
      return
    }
    
    var rows = data.logs || []
    var total = data.total || 0
    perPage = data.per_page || perPage
    var totalPages = Math.ceil(total / perPage)
    if (!totalPages) totalPages = 1
    if (page > totalPages) {
      window._LS_V2_LOGS_PAGE = totalPages
      return _lsv2RenderLogs()
    }
    var startIdx = (page - 1) * perPage + 1

    var statusTone = function (st) {
      var s = String(st || '').toLowerCase()
      if (s === 'processed') return 'ok'
      if (s === 'duplicate') return 'warn'
      if (s === 'error') return 'err'
      return 'warn'
    }

    var dateLine = function (iso) {
      if (!iso) return '-'
      var text = String(iso).trim()
      // Backend returns naive UTC timestamps without timezone suffix; treat them as UTC.
      if (text && !/(Z|[+-]\d\d:\d\d)$/i.test(text)) text += 'Z'
      var d = new Date(text)
      if (isNaN(d.getTime())) return '-'
      return d.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      }).replace(/,/g, '')
    }
    
    var bodyRows = rows.map(function (r, idx) {
      var sourceName = _lsv2LabelOr(r.source_name || r.source_type, 'Unknown Source')
      var sourceStatus = _lsv2LabelOr(r.source_status, 'Archived Source')
      var leadName = _lsv2LabelOr(r.lead_name, 'Unknown Lead')
      var leadPhone = _lsv2LabelOr(r.lead_phone, '—')
      var received = dateLine(r.received_at)
      return '<tr>' +
        '<td><strong>' + (startIdx + idx) + '</strong></td>' +
        '<td style="text-align:left">' +
          '<div style="font-weight:700">' + _lsv2Esc(leadName) + '</div>' +
          '<div class="lsv2-muted">' + _lsv2Esc(received) + '</div>' +
        '</td>' +
        '<td>' + _lsv2Esc(leadPhone) + '</td>' +
        '<td>' + _lsv2Esc(_lsv2LabelOr(r.project_name, 'No Project Assigned')) + '</td>' +
        '<td>' + _lsv2Esc(sourceName) + '</td>' +
        '<td>' + _lsv2Esc(_lsv2LabelOr(r.form_name, 'Attribution Pending')) + '</td>' +
        '<td>' + _lsv2Esc(_lsv2LabelOr(r.campaign_name, 'Attribution Pending')) + '</td>' +
        '<td>' + _lsv2Esc(sourceStatus) + '</td>' +
        '<td><span class="lsv2-badge ' + statusTone(r.status) + '">' + _lsv2Esc(r.status || '-') + '</span></td>' +
      '</tr>'
    }).join('')

    var pagerButtons = ''
    var fromPage = Math.max(1, page - 2)
    var toPage = Math.min(totalPages, fromPage + 4)
    fromPage = Math.max(1, toPage - 4)
    for (var p = fromPage; p <= toPage; p += 1) {
      var active = p === page
      pagerButtons += '<button class="lsv2-btn' + (active ? ' primary' : '') + '" onclick="_lsv2LogsGotoPage(' + p + ')">' + p + '</button>'
    }
    
    var paginationHtml = '<div class="lsv2-logs-pagination">' +
      '<div class="lsv2-logs-pagination-left">' +
        '<button class="lsv2-btn" onclick="_lsv2LogsPrevPage()" ' + (page <= 1 ? 'disabled' : '') + '>Prev</button>' +
        pagerButtons +
        '<button class="lsv2-btn" onclick="_lsv2LogsNextPage()" ' + (page >= totalPages ? 'disabled' : '') + '>Next</button>' +
      '</div>' +
      '<div class="lsv2-logs-pagination-right">' +
        '<span class="lsv2-muted">Showing ' + (rows.length ? startIdx : 0) + ' - ' + (rows.length ? (startIdx + rows.length - 1) : 0) + ' of ' + total + ' source leads</span>' +
        '<label class="lsv2-muted" for="lsv2-logs-per-page" style="margin:0">Rows</label>' +
        '<select id="lsv2-logs-per-page" class="form-select form-select-sm lsv2-input-compact" style="width:auto">' +
          '<option value="25" ' + (perPage === 25 ? 'selected' : '') + '>25</option>' +
          '<option value="50" ' + (perPage === 50 ? 'selected' : '') + '>50</option>' +
          '<option value="100" ' + (perPage === 100 ? 'selected' : '') + '>100</option>' +
        '</select>' +
      '</div>' +
      '</div>'
    
    var filterHtml = '<div class="lsv2-card lsv2-logs-filter-card">' +
      '<div class="lsv2-logs-filter-grid">' +
        '<div class="lsv2-logs-field field-wide"><label class="form-label" for="lsv2-logs-q">Search</label><input id="lsv2-logs-q" class="form-control form-select-sm lsv2-input-compact" type="text" value="' + _lsv2Esc(searchQ) + '" placeholder="lead, project, campaign, form"></div>' +
        '<div class="lsv2-logs-field field-mid"><label class="form-label" for="lsv2-logs-status">Status</label><select id="lsv2-logs-status" class="form-select form-select-sm lsv2-input-compact"><option value="">All</option><option value="processed" ' + (statusFilter === 'processed' ? 'selected' : '') + '>Processed</option><option value="duplicate" ' + (statusFilter === 'duplicate' ? 'selected' : '') + '>Duplicate</option><option value="error" ' + (statusFilter === 'error' ? 'selected' : '') + '>Error</option></select></div>' +
        '<div class="lsv2-logs-field field-mid" style="display:none"><input id="lsv2-logs-from" type="hidden" value="' + _lsv2Esc(dateFrom) + '"></div>' +
        '<div class="lsv2-logs-field field-mid" style="display:none"><input id="lsv2-logs-to" type="hidden" value="' + _lsv2Esc(dateTo) + '"></div>' +
        '<label class="lsv2-logs-filter-toggle"><input id="lsv2-logs-show-test" type="checkbox" ' + (showTestData ? 'checked' : '') + '> Show Test Data</label>' +
        '<div class="lsv2-logs-filter-actions"><button id="lsv2-logs-filter-btn" class="lsv2-btn primary">Apply Filters</button><button id="lsv2-logs-clear-btn" class="lsv2-btn subtle">Clear</button></div>' +
      '</div>' +
      '<div class="lsv2-muted" style="margin-top:8px">Validation, proof, and other test rows are hidden unless Show Test Data is enabled.</div>' +
      '</div>'
    
    _lsv2SetBody(
      filterHtml +
      '<div class="lsv2-card lsv2-logs-actions">' +
        '<div class="lsv2-logs-actions-inner">' +
          '<div class="lsv2-logs-bulk">' +
            '<span class="lsv2-muted">One row per unique source lead from connected sources.</span>' +
          '</div>' +
          '<button id="lsv2-logs-export-csv" class="lsv2-btn subtle lsv2-logs-download">Download CSV</button>' +
        '</div>' +
      '</div>' +
      '<div class="lsv2-table-wrap logs"><table class="lsv2-table"><thead><tr><th>#</th><th>Lead</th><th>Mobile</th><th>Project</th><th>Source</th><th>Form</th><th>Campaign</th><th>Source Status</th><th>Status</th></tr></thead><tbody>' + bodyRows + '</tbody></table></div>' +
      paginationHtml
    )
    
    var filterBtn = document.getElementById('lsv2-logs-filter-btn')
    var clearBtn = document.getElementById('lsv2-logs-clear-btn')
    var qInput = document.getElementById('lsv2-logs-q')
    var statusSel = document.getElementById('lsv2-logs-status')
    var fromInput = document.getElementById('lsv2-logs-from')
    var toInput = document.getElementById('lsv2-logs-to')
    var showTestInput = document.getElementById('lsv2-logs-show-test')
    var perPageSelect = document.getElementById('lsv2-logs-per-page')
    var exportCsvBtn = document.getElementById('lsv2-logs-export-csv')
    if (filterBtn) {
      filterBtn.addEventListener('click', function () {
        window._LS_V2_LOGS_Q = qInput.value
        window._LS_V2_LOGS_STATUS = statusSel.value
        window._LS_V2_LOGS_DATE_FROM = fromInput.value
        window._LS_V2_LOGS_DATE_TO = toInput.value
        _lsv2SetShowTestData(!!(showTestInput && showTestInput.checked))
        window._LS_V2_LOGS_PAGE = 1
        _lsv2RenderLogs()
      })
    }
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        window._LS_V2_LOGS_Q = ''
        window._LS_V2_LOGS_STATUS = ''
        window._LS_V2_LOGS_DATE_FROM = ''
        window._LS_V2_LOGS_DATE_TO = ''
        _lsv2SetShowTestData(false)
        window._LS_V2_LOGS_PAGE = 1
        _lsv2RenderLogs()
      })
    }
    if (exportCsvBtn) {
      exportCsvBtn.addEventListener('click', function () {
        _lsv2DownloadFile('/api/lead-sources/logs/export.csv' + (exportQuery ? ('?' + exportQuery) : ''), 'lead-source-logs.csv')
      })
    }

    if (perPageSelect) {
      perPageSelect.addEventListener('change', function () {
        window._LS_V2_LOGS_PER_PAGE = Number(perPageSelect.value || 25)
        window._LS_V2_LOGS_PAGE = 1
        _lsv2RenderLogs()
      })
    }

    updateSelectedCount()
  }
  
  function _lsv2LogsPrevPage() {
    var page = Number(window._LS_V2_LOGS_PAGE || 1)
    if (page > 1) {
      window._LS_V2_LOGS_PAGE = page - 1
      _lsv2RenderLogs()
    }
  }

  function _lsv2LogsGotoPage(nextPage) {
    var p = Number(nextPage || 1)
    if (!Number.isFinite(p) || p < 1) p = 1
    window._LS_V2_LOGS_PAGE = p
    _lsv2RenderLogs()
  }
  
  function _lsv2LogsNextPage() {
    var page = Number(window._LS_V2_LOGS_PAGE || 1)
    window._LS_V2_LOGS_PAGE = page + 1
    _lsv2RenderLogs()
  }

  window._lsv2LogsPrevPage = _lsv2LogsPrevPage
  window._lsv2LogsGotoPage = _lsv2LogsGotoPage
  window._lsv2LogsNextPage = _lsv2LogsNextPage

  async function _lsv2RenderReports() {
    if (!_lsv2ViewIs('reports')) return

    var srcPage = Number(window._LS_V2_REPORTS_SOURCE_PAGE || 1)
    if (!Number.isFinite(srcPage) || srcPage < 1) srcPage = 1
    var srcPerPage = Number(window._LS_V2_REPORTS_SOURCE_PER_PAGE || 10)
    if (![10, 25, 50, 100].includes(srcPerPage)) srcPerPage = 10
    var commonDateFrom = String(window._LS_V2_REPORTS_DATE_FROM || window._LS_V2_REPORTS_SOURCE_DATE_FROM || '').trim()
    var commonDateTo = String(window._LS_V2_REPORTS_DATE_TO || window._LS_V2_REPORTS_SOURCE_DATE_TO || '').trim()
    var commonShowTest = String(window._LS_V2_REPORTS_SHOW_TEST || window._LS_V2_REPORTS_SOURCE_SHOW_TEST || '').toLowerCase() === '1'
    var commonExportFormat = String(window._LS_V2_REPORTS_EXPORT_FORMAT || window._LS_V2_REPORTS_SOURCE_EXPORT_FORMAT || 'csv')

    window._LS_V2_REPORTS_DATE_FROM = commonDateFrom
    window._LS_V2_REPORTS_DATE_TO = commonDateTo
    window._LS_V2_REPORTS_SHOW_TEST = commonShowTest ? '1' : ''
    window._LS_V2_REPORTS_SOURCE_DATE_FROM = commonDateFrom
    window._LS_V2_REPORTS_SOURCE_DATE_TO = commonDateTo
    window._LS_V2_REPORTS_SOURCE_SHOW_TEST = commonShowTest ? '1' : ''

    var reportParams = new URLSearchParams()
    reportParams.append('source_page', srcPage)
    reportParams.append('source_per_page', srcPerPage)
    if (commonDateFrom) reportParams.append('date_from', commonDateFrom)
    if (commonDateTo) reportParams.append('date_to', commonDateTo)
    if (commonShowTest) reportParams.append('show_test_data', '1')

    var reportPayload = await _lsv2FetchReport('/api/lead-sources/reports/performance?' + reportParams.toString())
    if (!_lsv2ViewIs('reports')) return
    var reportData = reportPayload.data || {}
    if (!_lsv2ViewIs('reports')) return

    if (!reportPayload.ok) {
      _lsv2SetBody('<div class="alert alert-danger">Unable to load reports</div>')
      return
    }

    var overview = reportData.snapshot || {}

    var hasCustomKpiWindow = !!(commonDateFrom || commonDateTo)
    var kpiWindowLabel = hasCustomKpiWindow
      ? ((commonDateFrom || 'Start') + ' to ' + (commonDateTo || 'Today'))
      : 'All time'

    var fmtNum = function (v, digits) {
      if (v === null || v === undefined || v === '') return '-'
      var n = Number(v)
      if (!Number.isFinite(n)) return _lsv2Esc(String(v))
      return n.toLocaleString(undefined, {
        minimumFractionDigits: digits || 0,
        maximumFractionDigits: digits || 0,
      })
    }

    var kpiHtml = [
      ['Submissions', overview.total_leads || overview.total || 0, ''],
      ['Unique Leads', overview.unique_leads || 0, ''],
      ['Processed', overview.processed || 0, 'ok'],
      ['Duplicate', overview.duplicate || 0, 'warn'],
      ['Errors', overview.errors || 0, 'err'],
      ['Conversion %', fmtNum(overview.conversion_rate || 0, 2), ''],
      ['Spend', fmtNum(overview.spend, 2), ''],
      ['CPL', fmtNum(overview.cpl, 2), ''],
    ].map(function (k) {
      return '<div class="lsv2-kpi-card"><div class="lsv2-kpi-label">' + _lsv2Esc(k[0]) + '</div><div class="lsv2-kpi-value ' + _lsv2Esc(k[2]) + '">' + _lsv2Esc(k[1]) + '</div></div>'
    }).join('')

    var sourceRowsData = reportData.source_rows || []
    var formRowsData = reportData.form_rows || []
    var sourceTotal = Number(reportData.source_total || sourceRowsData.length)
    var sourceApiPerPage = Number(reportData.source_per_page || srcPerPage)
    if (![10, 25, 50, 100].includes(sourceApiPerPage)) sourceApiPerPage = srcPerPage
    var sourceTotalPages = Math.max(1, Math.ceil(sourceTotal / sourceApiPerPage))
    if (srcPage > sourceTotalPages) srcPage = sourceTotalPages

    var dateLine = function (iso) {
      if (!iso) return '-'
      var text = String(iso).trim()
      // Backend returns naive UTC timestamps without timezone suffix; treat them as UTC.
      if (text && !/(Z|[+-]\d\d:\d\d)$/i.test(text)) text += 'Z'
      var d = new Date(text)
      if (isNaN(d.getTime())) return '-'
      return d.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true }).replace(/,/g, '')
    }
    
    var sourceRows = sourceRowsData.map(function (r) {
      return '<tr>' +
        '<td>' + _lsv2Esc(_lsv2LabelOr(r.source_name, 'Unknown Source')) + '</td>' +
        '<td>' + Number(r.total_leads || r.total || 0) + '</td>' +
        '<td style="white-space:nowrap;">' + _lsv2Esc(dateLine(r.source_added_at)) + '</td>' +
        '<td style="white-space:nowrap;">' + _lsv2Esc(dateLine(r.last_sync)) + '</td>' +
        '<td>' + fmtNum(r.spend, 2) + '</td>' +
        '<td>' + Number(r.unique_leads || 0) + '</td>' +
        '<td>' + Number(r.processed || r.created || r.leads || 0) + '</td>' +
        '<td>' + Number(r.duplicate || r.duplicates || 0) + '</td>' +
        '<td>' + Number(r.errors || 0) + '</td>' +
        '<td>' + fmtNum(r.conversion_rate, 2) + '</td>' +
        '<td>' + fmtNum(r.cpl, 2) + '</td>' +
      '</tr>'
    }).join('')

    var formRows = formRowsData.map(function (r) {
      return '<tr>' +
        '<td>' + _lsv2Esc(_lsv2LabelOr(r.source_name, 'Unknown Source')) + '</td>' +
        '<td>' + _lsv2Esc(_lsv2LabelOr(r.form_name, 'Unknown Form')) + '</td>' +
        '<td>' + Number(r.total_leads || r.total || 0) + '</td>' +
        '<td>' + Number(r.unique_leads || 0) + '</td>' +
        '<td>' + Number(r.processed || r.created || r.leads || 0) + '</td>' +
        '<td>' + Number(r.duplicate || r.duplicates || 0) + '</td>' +
        '<td>' + Number(r.errors || 0) + '</td>' +
        '<td>' + fmtNum(r.conversion_rate, 2) + '</td>' +
      '</tr>'
    }).join('')

    var sourceExportFormat = commonExportFormat

    var syncBusy = window._LS_V2_REPORTS_META_SYNC_BUSY === '1'
    var syncLabel = syncBusy ? 'Syncing...' : 'Sync from Meta'
    var syncTitle = reportData.last_synced_at ? ('Last synced: ' + dateLine(reportData.last_synced_at)) : 'Fetch latest Meta insights for this report window'
    var syncButtonHtml = '<button id="lsv2ReportsMetaSyncBtn" class="lsv2-btn primary" title="' + _lsv2Esc(syncTitle) + '" ' + (syncBusy ? 'disabled' : '') + '>' + _lsv2Esc(syncLabel) + '</button>'
    var globalControlHtml = _lsv2RenderReportRangePicker('source', commonDateFrom, commonDateTo, commonShowTest, sourceExportFormat, syncButtonHtml)

    var sourcePagerButtons = ''
    var srcFromPage = Math.max(1, srcPage - 2)
    var srcToPage = Math.min(sourceTotalPages, srcFromPage + 4)
    srcFromPage = Math.max(1, srcToPage - 4)
    for (var sp = srcFromPage; sp <= srcToPage; sp += 1) {
      var sourceActive = sp === srcPage
      sourcePagerButtons += '<button class="lsv2-btn page' + (sourceActive ? ' primary' : '') + '" onclick="_lsv2ReportsSourceGotoPage(' + sp + ')">' + sp + '</button>'
    }

    var sourcePaginationHtml = '<div class="lsv2-reports-pagination">' +
      '<div class="lsv2-reports-pagination-left">' +
      '<button class="lsv2-btn" onclick="_lsv2ReportsSourcePrevPage()" ' + (srcPage <= 1 ? 'disabled' : '') + '>Prev</button>' +
      sourcePagerButtons +
      '<button class="lsv2-btn" onclick="_lsv2ReportsSourceNextPage()" ' + (srcPage >= sourceTotalPages ? 'disabled' : '') + '>Next</button>' +
      '</div>' +
      '<div class="lsv2-reports-pagination-right">' +
      '<span class="lsv2-muted">Showing ' + (sourceRowsData.length ? (((srcPage - 1) * sourceApiPerPage) + 1) : 0) + ' - ' + (sourceRowsData.length ? (((srcPage - 1) * sourceApiPerPage) + sourceRowsData.length) : 0) + ' of ' + sourceTotal + ' rows</span>' +
      '<label class="lsv2-muted" for="lsv2-reports-source-per-page" style="margin:0">Rows</label>' +
      '<select id="lsv2-reports-source-per-page" class="form-select form-select-sm lsv2-input-compact" style="width:auto">' +
      '<option value="10" ' + (sourceApiPerPage === 10 ? 'selected' : '') + '>10</option>' +
      '<option value="25" ' + (sourceApiPerPage === 25 ? 'selected' : '') + '>25</option>' +
      '<option value="50" ' + (sourceApiPerPage === 50 ? 'selected' : '') + '>50</option>' +
      '<option value="100" ' + (sourceApiPerPage === 100 ? 'selected' : '') + '>100</option>' +
      '</select>' +
      '</div>' +
      '</div>'

    _lsv2SetBody(
      '<div class="lsv2-kpi-head"><h4 class="lsv2-kpi-title">Performance Snapshot</h4><div class="lsv2-reports-global-controls">' + globalControlHtml + '</div></div>' +
      '<div class="lsv2-kpi-strip">' + kpiHtml + '</div>' +
      '<div class="lsv2-card lsv2-reports-filter-card" style="margin-bottom:12px"><h4 style="margin:0 0 6px">Source Performance</h4><div class="lsv2-table-wrap"><table class="lsv2-table"><thead><tr><th>Source</th><th>Submissions</th><th>Source Created</th><th>Last Sync</th><th>Spend</th><th>Unique Leads</th><th>Processed</th><th>Duplicate</th><th>Errors</th><th>Conversion %</th><th>CPL</th></tr></thead><tbody>' + sourceRows + '</tbody></table></div>' + sourcePaginationHtml + '</div>' +
      '<div class="lsv2-card lsv2-reports-filter-card" style="margin-bottom:12px"><h4 style="margin:0 0 6px">Forms</h4><div class="lsv2-table-wrap"><table class="lsv2-table"><thead><tr><th>Source</th><th>Form</th><th>Submissions</th><th>Unique Leads</th><th>Processed</th><th>Duplicate</th><th>Errors</th><th>Conversion %</th></tr></thead><tbody>' + formRows + '</tbody></table></div></div>'
    )
    
    var srcRangeTrigger = document.getElementById('lsv2-reports-source-range-trigger')
    var srcFromInput = document.getElementById('lsv2-reports-source-from')
    var srcToInput = document.getElementById('lsv2-reports-source-to')
    var srcShowTestInput = document.getElementById('lsv2-reports-source-show-test')
    var srcPerPageSelect = document.getElementById('lsv2-reports-source-per-page')
    var srcRangeApply = document.getElementById('lsv2-reports-source-apply-btn')
    var srcRangeCancel = document.getElementById('lsv2-reports-source-cancel-btn')
    var srcRangeClear = document.getElementById('lsv2-reports-source-clear-btn')
    var srcExportBtn = document.getElementById('lsv2-reports-source-export-btn')
    var srcExportFormat = document.getElementById('lsv2-reports-source-export-format')

    var metaSyncBtn = document.getElementById('lsv2ReportsMetaSyncBtn')

    if (metaSyncBtn) {
      metaSyncBtn.addEventListener('click', async function () {
        if (window._LS_V2_REPORTS_META_SYNC_BUSY === '1') return
        window._LS_V2_REPORTS_META_SYNC_BUSY = '1'
        metaSyncBtn.disabled = true
        metaSyncBtn.textContent = 'Syncing...'
        try {
          var syncRes = await authFetch('/api/lead-sources/reports/sync-meta', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              date_from: commonDateFrom,
              date_to: commonDateTo,
              show_test_data: commonShowTest,
            }),
          })
          if (!syncRes.ok) {
            var syncErr = await _lsv2ReadJsonSafe(syncRes)
            throw new Error((syncErr && (syncErr.error || syncErr.message)) || 'Unable to sync Meta reports')
          }
        } catch (err) {
          alert(err.message || 'Unable to sync Meta reports')
        } finally {
          window._LS_V2_REPORTS_META_SYNC_BUSY = ''
          _lsv2ReportCacheClear()
          _lsv2RenderReports()
        }
      })
    }

    if (srcRangeTrigger) {
      srcRangeTrigger.addEventListener('click', function () {
        var opening = !_lsv2ReportRangeIsOpen('source')
        _lsv2ReportRangeOpen('source', opening)
        if (opening) {
          _lsv2ReportRangeInitDraft('source')
          _lsv2ReportRangeSet('source', 'MONTH_ANCHOR', _lsv2MonthStartYmd(_lsv2ReportRangeGet('source', 'DRAFT_DATE_FROM') || _lsv2ReportRangeGet('source', 'DATE_FROM') || _lsv2TodayYmd()))
          _lsv2ReportRangeSyncUi('source')
        } else {
          _lsv2ReportRangeSetOpenUi('source', false)
        }
      })
    }
    if (srcFromInput) {
      srcFromInput.addEventListener('change', function () {
        _lsv2ReportRangeSet('source', 'DRAFT_DATE_FROM', srcFromInput.value)
      })
    }
    if (srcToInput) {
      srcToInput.addEventListener('change', function () {
        _lsv2ReportRangeSet('source', 'DRAFT_DATE_TO', srcToInput.value)
      })
    }
    if (srcRangeApply) {
      srcRangeApply.addEventListener('click', function () {
        if (srcFromInput) _lsv2ReportRangeSet('source', 'DRAFT_DATE_FROM', srcFromInput.value)
        if (srcToInput) _lsv2ReportRangeSet('source', 'DRAFT_DATE_TO', srcToInput.value)
        window._LS_V2_REPORTS_SOURCE_SHOW_TEST = (srcShowTestInput && srcShowTestInput.checked) ? '1' : ''
        window._LS_V2_REPORTS_SHOW_TEST = window._LS_V2_REPORTS_SOURCE_SHOW_TEST
        window._LS_V2_REPORTS_DATE_FROM = _lsv2ReportRangeGet('source', 'DRAFT_DATE_FROM')
        window._LS_V2_REPORTS_DATE_TO = _lsv2ReportRangeGet('source', 'DRAFT_DATE_TO')
        _lsv2ReportRangeApply('source')
      })
    }
    if (srcRangeCancel) {
      srcRangeCancel.addEventListener('click', function () {
        _lsv2ReportRangeOpen('source', false)
        _lsv2ReportRangeSetOpenUi('source', false)
      })
    }
    if (srcRangeClear) {
      srcRangeClear.addEventListener('click', function () {
        window._LS_V2_REPORTS_SOURCE_SHOW_TEST = (srcShowTestInput && srcShowTestInput.checked) ? '1' : ''
        window._LS_V2_REPORTS_SHOW_TEST = window._LS_V2_REPORTS_SOURCE_SHOW_TEST
        window._LS_V2_REPORTS_DATE_FROM = ''
        window._LS_V2_REPORTS_DATE_TO = ''
        _lsv2ReportRangeClear('source')
      })
    }
    if (srcPerPageSelect) {
      srcPerPageSelect.addEventListener('change', function () {
        window._LS_V2_REPORTS_SOURCE_PER_PAGE = Number(srcPerPageSelect.value || 10)
        window._LS_V2_REPORTS_SOURCE_PAGE = 1
        _lsv2RenderReports()
      })
    }
    if (srcShowTestInput) {
      srcShowTestInput.addEventListener('change', function () {
        window._LS_V2_REPORTS_SOURCE_SHOW_TEST = srcShowTestInput.checked ? '1' : ''
      })
    }
    if (srcExportFormat) {
      srcExportFormat.addEventListener('change', function () {
        window._LS_V2_REPORTS_SOURCE_EXPORT_FORMAT = srcExportFormat.value || 'csv'
        window._LS_V2_REPORTS_EXPORT_FORMAT = window._LS_V2_REPORTS_SOURCE_EXPORT_FORMAT
      })
    }
    if (srcExportBtn) {
      srcExportBtn.addEventListener('click', function () {
        var exportParams = new URLSearchParams()
        if (commonDateFrom) exportParams.append('date_from', commonDateFrom)
        if (commonDateTo) exportParams.append('date_to', commonDateTo)
        if (commonShowTest) exportParams.append('show_test_data', '1')
        var exportQuery = exportParams.toString()
        var fmt = String((srcExportFormat && srcExportFormat.value) || 'csv')
        var ext = fmt === 'xlsx' ? 'xlsx' : 'csv'
        _lsv2DownloadFile('/api/lead-sources/reports/by-source/export.' + ext + (exportQuery ? ('?' + exportQuery) : ''), 'lead-source-performance.' + ext)
      })
    }
  }

  function _lsv2ReportsSourcePrevPage() {
    var page = Number(window._LS_V2_REPORTS_SOURCE_PAGE || 1)
    if (page > 1) {
      window._LS_V2_REPORTS_SOURCE_PAGE = page - 1
      _lsv2RenderReports()
    }
  }

  function _lsv2ReportsSourceGotoPage(nextPage) {
    var p = Number(nextPage || 1)
    if (!Number.isFinite(p) || p < 1) p = 1
    window._LS_V2_REPORTS_SOURCE_PAGE = p
    _lsv2RenderReports()
  }

  function _lsv2ReportsSourceNextPage() {
    var page = Number(window._LS_V2_REPORTS_SOURCE_PAGE || 1)
    window._LS_V2_REPORTS_SOURCE_PAGE = page + 1
    _lsv2RenderReports()
  }

  window._lsv2ReportsSourcePrevPage = _lsv2ReportsSourcePrevPage
  window._lsv2ReportsSourceGotoPage = _lsv2ReportsSourceGotoPage
  window._lsv2ReportsSourceNextPage = _lsv2ReportsSourceNextPage

  async function _lsv2RenderBody(view) {
    if (view === 'sources') return _lsv2RenderSources()
    if (view === 'connect') return _lsv2RenderConnect()
    if (view === 'forms') return _lsv2RenderForms()
    if (view === 'validation') return _lsv2RenderValidation()
    if (view === 'logs') return _lsv2RenderLogs()
    if (view === 'reports') return _lsv2RenderReports()
    return _lsv2RenderSources()
  }

  function renderLeadSourcesV2() {
    var el = document.getElementById('content')
    if (!el) return

    _lsv2InstallStyles()
    var view = _lsv2CurrentView()

    el.innerHTML =
      '<div class="lsv2-wrap">' +
        '<div class="lsv2-top">' +
          '<div><h2>Leads Sources</h2><p>Route-based control center for source operations, validation and attribution.</p></div>' +
          '<div class="lsv2-actions"><button class="lsv2-btn" onclick="_lsv2Navigate(\'sources\')">Overview</button><button class="lsv2-btn primary" onclick="_lsv2Navigate(\'connect\')">Connect New</button></div>' +
        '</div>' +
        '<div id="lsv2-nav" class="lsv2-nav">' + _lsv2NavHtml(view) + '</div>' +
        '<div id="lsv2-body"></div>' +
      '</div>'

    _lsv2BindNav()
    _lsv2RenderBody(view)
  }

  async function _lsv2ToggleSource(id, enable) {
    var res = await authFetch('/api/lead-sources/' + id + '/' + (enable ? 'enable' : 'disable'), { method: 'POST' })
    var out = await _lsv2ReadJsonSafe(res)
    if (!res.ok) {
      if (typeof showToast === 'function') showToast(out.error || 'Failed to update source', 'danger')
      return
    }
    if (typeof showToast === 'function') showToast(enable ? 'Source enabled' : 'Source disabled', 'success')
    _lsv2RenderSources()
  }

  async function _lsv2TestSource(id) {
    var res = await authFetch('/api/lead-sources/' + id + '/test', { method: 'POST' })
    var out = await _lsv2ReadJsonSafe(res)
    var t = out.test || {}
    if (!res.ok) {
      if (typeof showToast === 'function') showToast(out.error || 'Test failed', 'danger')
      return
    }
    if (typeof showToast === 'function') showToast('Test: ' + (t.result || 'done') + ' - ' + (t.message || ''), t.result === 'pass' ? 'success' : 'warning')
    _lsv2RenderSources()
  }

  async function _lsv2DeleteSource(id, name) {
    if (!confirm('Are you sure you want to permanently delete the source "' + name + '"? This action cannot be undone. All form mappings and campaign snapshots will also be deleted.')) {
      return
    }
    var res = await authFetch('/api/lead-sources/' + id + '/hard-delete', { method: 'POST' })
    var out = await _lsv2ReadJsonSafe(res)
    if (!res.ok) {
      if (typeof showToast === 'function') showToast(out.error || 'Failed to delete source', 'danger')
      return
    }
    if (typeof showToast === 'function') showToast('Source deleted successfully', 'success')
    _lsv2RenderSources()
  }

  function _lsv2GoMappings(sourceId) {
    window._LS_V2_SELECTED_SOURCE_ID = Number(sourceId || 0)
    _lsv2Navigate('forms')
  }

  window.renderLeadSourcesV2 = renderLeadSourcesV2
  window._lsv2Navigate = _lsv2Navigate
  window._lsv2ToggleSource = _lsv2ToggleSource
  window._lsv2DeleteSource = _lsv2DeleteSource
  window._lsv2TestSource = _lsv2TestSource
  window._lsv2GoMappings = _lsv2GoMappings
  window._lsv2RefreshMetaForms = _lsv2RefreshMetaForms
  window._lsv2CloseModal = _lsv2CloseModal
  window._lsv2ShowMetaConnectionInfo = _lsv2ShowMetaConnectionInfo
  window._lsv2OpenMetaPageAdd = _lsv2OpenMetaPageAdd
  window._lsv2LoadMetaPageForms = _lsv2LoadMetaPageForms
  window._lsv2SaveMetaPageForms = _lsv2SaveMetaPageForms
})()
