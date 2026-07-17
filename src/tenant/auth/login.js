function renderLogin(context) {
  var publicRoot = document.getElementById('publicLoginRoot')
  if (!publicRoot) {
    publicRoot = document.createElement('div')
    publicRoot.id = 'publicLoginRoot'
    publicRoot.style.minHeight = '100vh'
    publicRoot.style.width = '100%'
    publicRoot.style.display = 'block'
    document.body.appendChild(publicRoot)
  }

  // Auto-detect context from URL when not explicitly provided
  if (!context) {
    var path = window.location.pathname.replace(/\/+$/, '')
    var appTenantLoginM = path.match(/^\/apps\/([^\/]+)\/([^\/]+)\/login$/)
    var appTenantM = path.match(/^\/apps\/([^\/]+)\/([^\/]+)$/)
    var tenantSimpleLoginM = path.match(/^\/([^\/]+)\/login$/)
    var tenantM = path.match(/^\/([^\/]+)(?:\/([^\/]+))?$/)
    var platformPaths = ['applications', 'organizations', 'analytics', 'settings', 'products', 'login']
    var demoLoginM = (path === '/demo/login') ? ['demo/login', 'lms'] : path.match(/^\/demo\/([^\/]+)\/login$/)
    var isPlatformPath = path === '/login' || platformPaths.indexOf((tenantM || [])[1]) !== -1
    if (demoLoginM) {
      context = { type: 'demo', product: 'lms' }
    } else
    if (!isPlatformPath && appTenantLoginM) {
      context = { type: 'tenant', slug: authCanonicalTenantSlug(appTenantLoginM[2]), product: appTenantLoginM[1] }
    } else
    if (!isPlatformPath && appTenantM) {
      context = { type: 'tenant', slug: authCanonicalTenantSlug(appTenantM[2]), product: appTenantM[1] }
    } else
    if (!isPlatformPath && tenantSimpleLoginM) {
      if (tenantSimpleLoginM[1] === 'demo') context = { type: 'demo', product: 'lms' }
      else context = { type: 'tenant', slug: authCanonicalTenantSlug(tenantSimpleLoginM[1]), product: 'lms' }
    } else
    if (!isPlatformPath && tenantM) {
      if (tenantM[1] === 'demo') context = { type: 'demo', product: 'lms' }
      else context = { type: 'tenant', slug: authCanonicalTenantSlug(tenantM[1]), product: 'lms' }
    } else {
      context = { type: 'platform' }
    }
  }

  var isPlatform = context.type === 'platform'
  var isDemo = context.type === 'demo'
  var loginContext = isPlatform ? 'platform' : (isDemo ? 'demo' : 'tenant')
  var tenantSlug  = (!isPlatform && !isDemo && context.slug) ? context.slug : null
  var tenantDataSlug = tenantSlug ? authTenantDataSlug(tenantSlug) : null
  var productSlug = context.product || 'lms'

  // Persist tenant hint whenever tenant login UI is rendered so LMS PWA launch
  // can recover tenant context even after Safari -> standalone transitions.
  if (tenantSlug) {
    try {
      var canonicalTenant = authCanonicalTenantSlug(tenantSlug)
      if (canonicalTenant) {
        localStorage.setItem('lms_last_tenant_slug', canonicalTenant)
        document.cookie = 'lms_last_tenant_slug=' + encodeURIComponent(canonicalTenant) + '; Path=/; Max-Age=2592000; SameSite=Lax; Secure'
      }
    } catch (_e) {}
  }

  // Resolve tenant branding (tenantConfig may have been loaded by dispatch())
  var tenantLogoSrc  = isDemo
    ? 'Assets/credentials-card-logo.png'
    : ((typeof tenantConfig !== 'undefined' && tenantConfig && tenantConfig.logo_url)
      ? tenantConfig.logo_url : 'logo.jpg')
  var _tenantFallbackBrand = isDemo
    ? 'LMS Demo'
    : (tenantSlug
      ? authCanonicalTenantSlug(tenantSlug).replace(/-/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase() })
      : 'Enterprise Lead Management')
  var tenantBrandName = (typeof tenantConfig !== 'undefined' && tenantConfig && (tenantConfig.brand_name || tenantConfig.name))
                       ? (tenantConfig.brand_name || tenantConfig.name) : _tenantFallbackBrand
  var loginBg = (typeof tenantConfig !== 'undefined' && tenantConfig && tenantConfig.login_bg_color)
                       ? tenantConfig.login_bg_color : '#ffffff'

  // Platform logo shown above the login card (no banner background)
  var monkeyIconHtml =
    '<img src="Assets/top-banner-logo.png" alt="Sociomonkey" style="height:62px;width:62px;object-fit:contain;display:block;margin:0 auto;" />'

  // Build header HTML — platform: SOCIO MONKEY logo image; tenant: logo + brand name
  var headerHtml = isPlatform
    ? '<div style="text-align:center;margin-bottom:24px;">' +
      '<img src="Assets/credentials-card-logo.png" alt="Sociomonkey" ' +
      'style="height:112px;width:auto;max-width:100%;display:block;margin:0 auto;" /></div>'
    : '<img src="' + tenantLogoSrc + '" alt="' + tenantBrandName + '" style="width:160px;height:auto;border-radius:10px;display:block;margin:0 auto 16px;" /><h3 style="text-align:center;font-size:18px;font-weight:700;color:#111111;">' + tenantBrandName + '</h3>'

  // Hide sidebar during login
  var sidebar = document.querySelector('.sm-sidebar')
  if (sidebar) sidebar.style.display = 'none'
  var mainContent = document.querySelector('.main-content')
  if (mainContent) mainContent.style.marginLeft = '0'
  // Kill scroll and force white background during login
  var bgColor = isPlatform ? '#ffffff' : loginBg
  document.body.style.margin = '0'
  document.body.style.padding = '0'
  document.documentElement.style.margin = '0'
  document.documentElement.style.padding = '0'
  document.body.style.background = bgColor
  document.body.style.overflow = 'hidden'
  document.documentElement.style.overflow = 'hidden'
  if (mainContent) {
    mainContent.style.background = bgColor
    mainContent.style.overflow = 'hidden'
    mainContent.style.height = '100vh'
  }
  if (root) {
    root.style.padding = '0'
    root.style.height = '100vh'
    root.style.overflow = 'hidden'
  }

  // Default auth mode across platform and tenant apps: password first.
  var otpDisplay      = 'none'
  var passwordDisplay = 'block'

  publicRoot.innerHTML =
    '<div style="display:flex;flex-direction:column;width:100%;height:100vh;overflow:hidden;background:' + bgColor + ';">' +
      (isPlatform
        ? '<div style="padding:18px 0 6px;display:flex;align-items:center;justify-content:center;flex-shrink:0;">' + monkeyIconHtml + '</div>'
        : '') +
      '<div style="flex:1;display:flex;align-items:center;justify-content:center;padding:24px;overflow-y:auto;">' +
        '<div class="card" style="max-width:400px;width:100%;margin:0;">' +
          headerHtml +
        // OTP section — secondary sign-in option
        '<div id="otpSection" style="display:' + otpDisplay + ';margin-top:24px;">' +
          '<div id="otpStep1">' +
            '<p style="color:#334155;font-size:14px;text-align:center;margin-bottom:16px;">' +
              'Enter your email to receive a one-time login code.</p>' +
            '<input class="input" id="otpEmail" type="email" placeholder="Your email address" ' +
              'autocomplete="email" />' +
            '<label style="display:flex;align-items:center;gap:8px;margin-top:10px;' +
              'font-size:13px;color:#64748b;cursor:pointer;">' +
              '<input type="checkbox" id="rememberMeOtpCheck" checked ' +
                'style="width:15px;height:15px;cursor:pointer;" />' +
              'Keep me signed in' +
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
          '<div style="text-align:center;margin-top:18px;">' +
            '<a href="#" id="switchToPassword" style="font-size:12px;color:#94a3b8;">' +
            'Sign in with password</a></div>' +
        '</div>' +
        // Password section — default sign-in mode for all contexts
        '<div id="passwordSection" style="display:' + passwordDisplay + ';margin-top:24px;">' +
          '<form id="loginForm">' +
            '<input class="input" id="email" type="email" placeholder="Email" ' +
              'autocomplete="email" required />' +
            '<div style="position:relative;display:flex;align-items:center;">' +
              '<input class="input" id="password" type="password" placeholder="Password" ' +
                'autocomplete="current-password" required style="padding-right:40px;flex:1;" />' +
              '<button type="button" id="togglePasswordBtn" aria-label="Toggle password visibility" ' +
                'style="position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;' +
                'border:none;cursor:pointer;padding:0;color:#94a3b8;font-size:17px;line-height:1;' +
                'display:flex;align-items:center;min-height:0;" tabindex="-1">👁</button>' +
            '</div>' +
              '<label style="display:flex;align-items:center;gap:8px;margin-top:10px;' +
              'font-size:13px;color:#64748b;cursor:pointer;">' +
              '<input type="checkbox" id="rememberMeCheck" checked ' +
                'style="width:15px;height:15px;cursor:pointer;" />' +
              'Keep me signed in' +
            '</label>' +
            '<button class="button" style="width:100%;margin-top:16px;font-size:15px;">' +
              'Login</button>' +
          '</form>' +
            '<div style="text-align:center;margin-top:12px;">' +
             '<a href="#" id="switchToOtp" style="font-size:13px;color:#0284c7;">' +
             'Login with OTP instead &rarr;</a></div>' +
        '</div>' +
        '<div id="loginError" style="color:#dc2626;text-align:center;' +
          'margin-top:12px;font-size:13px;min-height:18px;"></div>' +
        (isPlatform ? '' :
          '<div style="text-align:center;margin-top:20px;padding-top:14px;border-top:1px solid #f1f5f9;">' +
            '<span style="font-size:11px;color:#94a3b8;letter-spacing:0.04em;display:block;margin-bottom:6px;">Powered by</span>' +
            '<img src=\"Assets/credentials-card-logo.png\" alt=\"SocioMonkey\" style=\"height:55px;width:auto;opacity:0.85;\" />' +
          '</div>') +
      '</div>' +
    '</div>' +
  '</div>'

  // ── Helpers ────────────────────────────────────────────────────────────────
  function showError(msg) { var el = document.getElementById('loginError'); if (el) el.textContent = msg }
  function clearError()   { showError('') }

  var passwordInput = document.getElementById('password')
  var togglePasswordBtn = document.getElementById('togglePasswordBtn')
  if (passwordInput && togglePasswordBtn) {
    togglePasswordBtn.addEventListener('click', function() {
      var isHidden = passwordInput.type === 'password'
      passwordInput.type = isHidden ? 'text' : 'password'
      togglePasswordBtn.textContent = isHidden ? '🙈' : '👁'
      togglePasswordBtn.setAttribute('aria-label', isHidden ? 'Hide password' : 'Show password')
    })
  }

  // ── Password form submit ───────────────────────────────────────────────────
  document.getElementById('loginForm').addEventListener('submit', async function(e) {
    e.preventDefault()
    var emailVal    = document.getElementById('email').value
    var passwordVal = document.getElementById('password').value
    var remember    = document.getElementById('rememberMeCheck').checked
    clearError()
    await login(emailVal, passwordVal, remember, tenantDataSlug || tenantSlug, loginContext, productSlug)
  })

  // ── Toggle OTP ↔ Password ──────────────────────────────────────────────────
  var switchToOtpEl = document.getElementById('switchToOtp')
  if (switchToOtpEl) {
    switchToOtpEl.addEventListener('click', function(e) {
      e.preventDefault()
      document.getElementById('passwordSection').style.display = 'none'
      document.getElementById('otpSection').style.display = 'block'
      clearError()
    })
  }

  var switchToPasswordEl = document.getElementById('switchToPassword')
  if (switchToPasswordEl) {
    switchToPasswordEl.addEventListener('click', function(e) {
      e.preventDefault()
      document.getElementById('otpSection').style.display = 'none'
      document.getElementById('passwordSection').style.display = 'block'
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
      var body = { email: emailVal, tenant_slug: tenantDataSlug || '', login_context: loginContext, product_slug: productSlug }
      if (tenantDataSlug) body.tenant_slug = tenantDataSlug
      var res  = await fetch(API_BASE + '/auth/send-otp', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      var data = await res.json()
      if (!res.ok) {
        showError(data.message || data.error || 'Failed to send OTP. Please try again.')
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
      var body = { email: emailVal, otp: otpVal, remember: !!remember, tenant_slug: tenantDataSlug || '', login_context: loginContext, product_slug: productSlug }
      if (tenantDataSlug) body.tenant_slug = tenantDataSlug
      var res  = await fetch(API_BASE + '/auth/verify-otp', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      var data = await res.json()
      if (!res.ok) {
        showError(data.message || data.error || 'Invalid OTP. Please try again.')
        btn.disabled    = false
        btn.textContent = 'Verify & Login'
        return
      }
      clearInterval(_countdownTimer)
      authSetSession(data.token, data.user, remember, data.refresh_token || null, data.login_context || loginContext)
      try {
        if (typeof pushRequestPermission === 'function') {
          pushRequestPermission().catch(function () {})
        }
      } catch (_e) {}
      if (data.products) availableProducts = data.products
      authScheduleExpiry()
      if (loginRedirectPath && loginRedirectPath !== '/login' && !loginRedirectPath.endsWith('/login')) {
        history.pushState({}, '', loginRedirectPath)
        loginRedirectPath = ''
      } else if ((data.login_context || loginContext) === 'platform') {
        history.replaceState({}, '', '/')
      } else if ((data.login_context || loginContext) === 'tenant' && data.user && data.user.tenant_slug) {
        history.replaceState({}, '', authBuildTenantAppPath(data.user.tenant_slug, productSlug || 'lms'))
      } else if ((data.login_context || loginContext) === 'demo') {
        history.replaceState({}, '', '/demo')
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
