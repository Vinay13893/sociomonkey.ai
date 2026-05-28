function renderLogin(context) {
  // Auto-detect context from URL when not explicitly provided
  if (!context) {
    var path = window.location.pathname.replace(/\/+$/, '')
    var tenantSimpleLoginM = path.match(/^\/([^\/]+)\/login$/)
    var tenantM = path.match(/^\/([^\/]+)\/([^\/]+)(?:\/login)?$/)
    var platformPaths = ['applications', 'organizations', 'analytics', 'settings', 'products', 'login']
    var isPlatformPath = (!tenantM && !tenantSimpleLoginM) || path === '/login' || platformPaths.indexOf((tenantM || [])[1]) !== -1
    if (!isPlatformPath && tenantSimpleLoginM) {
      context = { type: 'tenant', slug: tenantSimpleLoginM[1], product: 'lms' }
    } else
    if (!isPlatformPath && tenantM) {
      context = { type: 'tenant', slug: tenantM[1], product: tenantM[2] }
    } else {
      context = { type: 'platform' }
    }
  }

  var isPlatform = context.type === 'platform'
  var tenantSlug  = (!isPlatform && context.slug) ? context.slug : null

  // Resolve tenant branding (tenantConfig may have been loaded by dispatch())
  var tenantLogoSrc  = (typeof tenantConfig !== 'undefined' && tenantConfig && tenantConfig.logo_url)
                       ? tenantConfig.logo_url : 'logo.jpg'
  var tenantBrandName = (typeof tenantConfig !== 'undefined' && tenantConfig && (tenantConfig.brand_name || tenantConfig.name))
                       ? (tenantConfig.brand_name || tenantConfig.name) : 'Enterprise Lead Management'
  var loginBg = (typeof tenantConfig !== 'undefined' && tenantConfig && tenantConfig.login_bg_color)
                       ? tenantConfig.login_bg_color : '#f1f5f9'

  // Build header HTML
  var headerHtml = isPlatform
    ? '<div style="text-align:center;margin-bottom:20px;"><div style="display:inline-flex;align-items:center;gap:10px;margin-bottom:8px;"><span style="font-size:32px;">&#x1F412;</span><span style="font-size:22px;font-weight:700;color:#1e293b;">sociomonkey.ai</span></div><p style="color:#64748b;font-size:13px;margin:0;">Platform Administration</p></div>'
    : '<img src="' + tenantLogoSrc + '" alt="' + tenantBrandName + '" style="width:160px;height:auto;border-radius:10px;display:block;margin:0 auto 16px;" /><h3 style="text-align:center;color:#64748b;">' + tenantBrandName + '</h3>'

  // Hide sidebar during login
  var sidebar = document.querySelector('.sidebar')
  if (sidebar) sidebar.style.display = 'none'
  var mainContent = document.querySelector('.main-content')
  if (mainContent) mainContent.style.marginLeft = '0'

  var otpDisplay      = isPlatform ? 'none'  : 'block'
  var passwordDisplay = isPlatform ? 'block' : 'none'

  root.innerHTML =
    '<div style="display:flex;align-items:center;justify-content:center;min-height:100vh;' +
    'background:' + (isPlatform ? '#f1f5f9' : loginBg) + ';">' +
      '<div class="card" style="max-width:420px;width:100%;">' +
        headerHtml +
        // OTP section — PRIMARY for tenant, HIDDEN for platform
        '<div id="otpSection" style="display:' + otpDisplay + ';margin-top:24px;">' +
          '<div id="otpStep1">' +
            '<p style="color:#334155;font-size:14px;text-align:center;margin-bottom:16px;">' +
              'Enter your email to receive a one-time login code.</p>' +
            '<input class="input" id="otpEmail" type="email" placeholder="Your email address" ' +
              'autocomplete="email" />' +
            '<label style="display:flex;align-items:center;gap:8px;margin-top:10px;' +
              'font-size:13px;color:#64748b;cursor:pointer;">' +
              '<input type="checkbox" id="rememberMeOtpCheck" ' +
                'style="width:15px;height:15px;cursor:pointer;" />' +
              'Remember me' +
            '</label>' +
            '<button id="sendOtpBtn" class="button" ' +
              'style="width:100%;margin-top:14px;font-size:15px;">Send OTP</button>' +
          '</div>' +
          '<div id="otpStep2" style="display:none;">' +
            '<p id="otpSentMsg" style="text-align:center;color:#16a34a;font-size:13px;' +
              'margin-bottom:14px;"></p>' +
            '<input class="input" id="otpCode" type="text" inputmode="numeric" maxlength="6" ' +
              'placeholder="6-digit OTP" autocomplete="one-time-code" ' +
              'style="letter-spacing:10px;font-size:22px;text-align:center;" />' +
            '<button id="verifyOtpBtn" class="button" ' +
              'style="width:100%;margin-top:14px;font-size:15px;">Verify &amp; Login</button>' +
            '<div style="text-align:center;margin-top:10px;min-height:20px;">' +
              '<span id="resendCountdown" style="font-size:12px;color:#64748b;display:none;">' +
                'Resend in <strong id="resendSec">30</strong>s' +
              '</span>' +
              '<a href="#" id="resendOtpLink" style="font-size:12px;color:#0284c7;' +
                'display:none;">Resend OTP</a>' +
            '</div>' +
          '</div>' +
          (isPlatform
            ? ''
            : ('<div style="text-align:center;margin-top:18px;">' +
               '<a href="#" id="switchToPassword" style="font-size:12px;color:#94a3b8;">' +
               'Sign in with password</a></div>')) +
        '</div>' +
        // Password section — PRIMARY for platform, HIDDEN for tenant
        '<div id="passwordSection" style="display:' + passwordDisplay + ';margin-top:24px;">' +
          '<form id="loginForm">' +
            '<input class="input" id="email" type="email" placeholder="Email" ' +
              'autocomplete="email" required />' +
            '<input class="input" id="password" type="password" placeholder="Password" ' +
              'autocomplete="current-password" required />' +
            '<label style="display:flex;align-items:center;gap:8px;margin-top:10px;' +
              'font-size:13px;color:#64748b;cursor:pointer;">' +
              '<input type="checkbox" id="rememberMeCheck" ' +
                'style="width:15px;height:15px;cursor:pointer;" />' +
              'Remember me' +
            '</label>' +
            '<button class="button" style="width:100%;margin-top:16px;font-size:15px;">' +
              'Login</button>' +
          '</form>' +
          (isPlatform
            ? ('<div style="text-align:center;margin-top:12px;">' +
               '<a href="#" id="switchToOtp" style="font-size:13px;color:#0284c7;">' +
               'Login with OTP instead &rarr;</a></div>')
            : ('<div style="text-align:center;margin-top:10px;">' +
               '<a href="#" id="backToOtp" style="font-size:12px;color:#0284c7;">' +
               '&larr; Back to OTP login</a></div>')) +
        '</div>' +
        '<div id="loginError" style="color:#dc2626;text-align:center;' +
          'margin-top:12px;font-size:13px;min-height:18px;"></div>' +
      '</div>' +
    '</div>'

  // ── Helpers ────────────────────────────────────────────────────────────────
  function showError(msg) { var el = document.getElementById('loginError'); if (el) el.textContent = msg }
  function clearError()   { showError('') }

  // ── Password form submit ───────────────────────────────────────────────────
  document.getElementById('loginForm').addEventListener('submit', async function(e) {
    e.preventDefault()
    var emailVal    = document.getElementById('email').value
    var passwordVal = document.getElementById('password').value
    var remember    = document.getElementById('rememberMeCheck').checked
    clearError()
    await login(emailVal, passwordVal, remember, tenantSlug)
  })

  // ── Toggle OTP ↔ Password ──────────────────────────────────────────────────
  if (isPlatform) {
    document.getElementById('switchToOtp').addEventListener('click', function(e) {
      e.preventDefault()
      document.getElementById('passwordSection').style.display = 'none'
      document.getElementById('otpSection').style.display = 'block'
      clearError()
    })
  } else {
    document.getElementById('switchToPassword').addEventListener('click', function(e) {
      e.preventDefault()
      document.getElementById('otpSection').style.display = 'none'
      document.getElementById('passwordSection').style.display = 'block'
      clearError()
    })
    document.getElementById('backToOtp').addEventListener('click', function(e) {
      e.preventDefault()
      document.getElementById('passwordSection').style.display = 'none'
      document.getElementById('otpSection').style.display = 'block'
      clearError()
    })
  }

  // ── Resend countdown timer ─────────────────────────────────────────────────
  var _countdownTimer = null
  function startResendCountdown(seconds) {
    var countdown  = document.getElementById('resendCountdown')
    var resendLink = document.getElementById('resendOtpLink')
    var secEl      = document.getElementById('resendSec')
    if (!countdown || !resendLink || !secEl) return
    countdown.style.display  = 'inline'
    resendLink.style.display = 'none'
    secEl.textContent = seconds
    clearInterval(_countdownTimer)
    var remaining = seconds
    _countdownTimer = setInterval(function() {
      remaining--
      if (secEl) secEl.textContent = remaining
      if (remaining <= 0) {
        clearInterval(_countdownTimer)
        if (countdown)  countdown.style.display  = 'none'
        if (resendLink) resendLink.style.display = 'inline'
      }
    }, 1000)
  }

  // ── Send OTP ───────────────────────────────────────────────────────────────
  async function sendOtp() {
    var emailVal = (document.getElementById('otpEmail').value || '').trim()
    if (!emailVal) { showError('Please enter your email address.'); return }
    var btn = document.getElementById('sendOtpBtn')
    btn.disabled    = true
    btn.textContent = 'Sending\u2026'
    clearError()
    try {
      var body = { email: emailVal }
      if (tenantSlug) body.tenant_slug = tenantSlug
      var res  = await fetch(API_BASE + '/auth/send-otp', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      var data = await res.json()
      if (!res.ok) {
        showError(data.error || 'Failed to send OTP. Please try again.')
        btn.disabled    = false
        btn.textContent = 'Send OTP'
        return
      }
      document.getElementById('otpStep1').style.display = 'none'
      document.getElementById('otpStep2').style.display = 'block'
      document.getElementById('otpSentMsg').textContent = '\u2713 OTP sent to ' + emailVal + '. Check your inbox.'
      var codeInput = document.getElementById('otpCode')
      if (codeInput) codeInput.focus()
      startResendCountdown(30)
    } catch (err) {
      showError('Network error. Please try again.')
      btn.disabled    = false
      btn.textContent = 'Send OTP'
    }
  }

  document.getElementById('sendOtpBtn').addEventListener('click', sendOtp)
  document.getElementById('otpEmail').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') { e.preventDefault(); sendOtp() }
  })

  // ── Resend OTP ─────────────────────────────────────────────────────────────
  document.getElementById('resendOtpLink').addEventListener('click', function(e) {
    e.preventDefault()
    clearInterval(_countdownTimer)
    document.getElementById('otpCode').value = ''
    document.getElementById('otpStep2').style.display = 'none'
    document.getElementById('otpStep1').style.display = 'block'
    var btn = document.getElementById('sendOtpBtn')
    btn.disabled    = false
    btn.textContent = 'Resend OTP'
    clearError()
  })

  // ── Verify OTP ─────────────────────────────────────────────────────────────
  async function verifyOtp() {
    var emailVal = (document.getElementById('otpEmail').value || '').trim()
    var otpVal   = (document.getElementById('otpCode').value  || '').trim()
    var remember = document.getElementById('rememberMeOtpCheck').checked
    if (!otpVal || otpVal.length < 6) { showError('Please enter the 6-digit OTP.'); return }
    var btn = document.getElementById('verifyOtpBtn')
    btn.disabled    = true
    btn.textContent = 'Verifying\u2026'
    clearError()
    try {
      var body = { email: emailVal, otp: otpVal }
      if (tenantSlug) body.tenant_slug = tenantSlug
      var res  = await fetch(API_BASE + '/auth/verify-otp', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      var data = await res.json()
      if (!res.ok) {
        showError(data.error || 'Invalid OTP. Please try again.')
        btn.disabled    = false
        btn.textContent = 'Verify & Login'
        return
      }
      clearInterval(_countdownTimer)
      authSetSession(data.token, data.user, remember)
      if (data.products) availableProducts = data.products
      authScheduleExpiry()
      if (loginRedirectPath && loginRedirectPath !== '/login' && !loginRedirectPath.endsWith('/login')) {
        history.pushState({}, '', loginRedirectPath)
        loginRedirectPath = ''
      }
      dispatch()
    } catch (err) {
      showError('Network error. Please try again.')
      btn.disabled    = false
      btn.textContent = 'Verify & Login'
    }
  }

  document.getElementById('verifyOtpBtn').addEventListener('click', verifyOtp)
  document.getElementById('otpCode').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') { e.preventDefault(); verifyOtp() }
  })
}
