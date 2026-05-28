// ============================================================================
// PERFORMANCE TRACER — diagnostic instrumentation
//
// Usage (browser DevTools console):
//   _PERF.report()          — print full waterfall
//   _PERF.enabled = false   — silence all instrumentation
//   _PERF.reset()           — clear and restart
//
// This file MUST be the first <script> loaded so _t0 is as early as possible.
// ============================================================================
;(function () {
  'use strict'

  // Capture absolute page-start reference as early as possible
  var _t0 = performance.now()
  var _enabled = true
  var _timeline = []   // { label, t, dur?, type: 'start'|'end'|'lap' }
  var _open = {}       // label → start_t (for mark/end pairs)
  var _counts = {}     // label → call count (duplicate detection)
  var _durations = {}  // label → last measured duration

  function _rel() {
    return +(performance.now() - _t0).toFixed(2)
  }

  // ── mark(label) ────────────────────────────────────────────────────────────
  // Start a named timer. Pair with end(label) to measure duration.
  function mark(label) {
    if (!_enabled) return
    if (_open[label] !== undefined) {
      console.warn('[perf] ' + label + ' already exists')
    }
    var t = _rel()
    _open[label] = t
    _timeline.push({ label: label, t: t, type: 'start' })
  }

  // ── cancel(label) ──────────────────────────────────────────────────────────
  // Silently remove an open mark without recording a duration.
  // Use this in abort paths where end() will never be called.
  function cancel(label) {
    if (!_enabled) return
    delete _open[label]
  }

  // ── end(label) → duration (ms) ─────────────────────────────────────────────
  // Stop a timer started with mark(). Returns elapsed ms.
  function end(label) {
    if (!_enabled) return 0
    var t = _rel()
    var start = _open[label]
    if (start === undefined) return 0
    var dur = +(t - start).toFixed(2)
    delete _open[label]
    _durations[label] = dur
    _timeline.push({ label: label, t: t, dur: dur, type: 'end' })
    return dur
  }

  // ── count(label) ───────────────────────────────────────────────────────────
  // Track how many times a function is called. Warns on > 1.
  function count(label) {
    if (!_enabled) return
    _counts[label] = (_counts[label] || 0) + 1
    if (_counts[label] > 1) {
      console.warn('[PERF] \u26A0 DUPLICATE CALL: ' + label + ' \xD7 ' + _counts[label])
    }
  }

  // ── lap(label, note) ───────────────────────────────────────────────────────
  // Record a timestamped waypoint / annotation on the timeline.
  function lap(label, note) {
    if (!_enabled) return
    _timeline.push({ label: label, t: _rel(), note: note || '', type: 'lap' })
  }

  // ── report() ───────────────────────────────────────────────────────────────
  // Print a structured waterfall to the browser console.
  function report() {
    var totalElapsed = +(performance.now() - _t0).toFixed(0)

    console.group(
      '%c\uD83D\uDD2C PERF WATERFALL',
      'color:#3b82f6;font-weight:bold;font-size:14px;font-family:monospace'
    )
    console.log('Time since first <script> loaded: ' + totalElapsed + 'ms\n')

    // ── Timeline ──
    console.log('%c\u25BC TIMELINE', 'font-weight:bold;font-family:monospace')
    _timeline.forEach(function (e) {
      var icon  = e.type === 'start' ? '\u25B6' : (e.type === 'end' ? '\u25C0' : '\u2022')
      var ts    = ('+' + e.t + 'ms').padStart(12)
      var dur   = e.dur !== undefined ? '  [' + e.dur + 'ms]' : ''
      var note  = e.note ? '  \u2014 ' + e.note : ''
      var style = e.type === 'end'
        ? 'color:#10b981;font-family:monospace'
        : (e.type === 'start' ? 'color:#3b82f6;font-family:monospace' : 'color:#64748b;font-family:monospace')
      console.log('%c ' + icon + ts + '  ' + e.label + dur + note, style)
    })

    // ── Call counts ──
    console.log('\n%c\u26A0 CALL COUNTS  (> 1 = DUPLICATE RENDER)', 'font-weight:bold;font-family:monospace')
    var ckeys = Object.keys(_counts).sort()
    if (!ckeys.length) {
      console.log('  (none recorded)')
    } else {
      ckeys.forEach(function (k) {
        var dup   = _counts[k] > 1
        var style = dup ? 'color:red;font-weight:bold;font-family:monospace' : 'font-family:monospace'
        console.log('%c  ' + (k + ':').padEnd(38) + _counts[k] + (dup ? '  \u26A0 DUPLICATE \xD7' + _counts[k] : ''), style)
      })
    }

    // ── Duration ranking ──
    console.log('\n%c\u23F1 DURATION RANKING  (slowest first)', 'font-weight:bold;font-family:monospace')
    var sorted = Object.keys(_durations).sort(function (a, b) {
      return _durations[b] - _durations[a]
    })
    if (!sorted.length) {
      console.log('  (none recorded)')
    } else {
      sorted.forEach(function (k) {
        var ms    = _durations[k]
        var style = ms > 1000
          ? 'color:red;font-weight:bold;font-family:monospace'
          : (ms > 100 ? 'color:#f59e0b;font-family:monospace' : 'color:#10b981;font-family:monospace')
        console.log('%c  ' + (k + ':').padEnd(38) + ms + 'ms', style)
      })
    }

    console.log('\nTotal elapsed: ' + totalElapsed + 'ms')
    console.groupEnd()
  }

  // ── Expose global ──────────────────────────────────────────────────────────
  window._PERF = {
    get enabled()    { return _enabled },
    set enabled(v)   { _enabled = !!v },
    mark:   mark,
    end:    end,
    count:  count,
    lap:    lap,
    cancel: cancel,
    report: report,
    reset: function () {
      _timeline = []; _open = {}; _counts = {}; _durations = {}
      _t0 = performance.now()
      mark('scripts:start')
    }
  }

  // First mark — as early in the script load sequence as possible
  mark('scripts:start')
})()
