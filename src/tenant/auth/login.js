function renderLogin(context) {
  // Auto-detect context from URL when not explicitly provided
  if (!context) {
    var path = window.location.pathname.replace(/\/+$/, '')
    var tenantSimpleLoginM = path.match(/^\/([^\/]+)\/login$/)
    var tenantM = path.match(/^\/([^\/]+)\/([^\/]+)(?:\/login)?$/)
    var platformPaths = ['applications', 'organizations', 'analytics', 'settings', 'products', 'login']
    var isPlatformPath = (!tenantM && !tenantSimpleLoginM) || path === '/login' || platformPaths.indexOf((tenantM || [])[1]) !== -1
    if (!isPlatformPath && tenantSimpleLoginM) {
      context = { type: 'tenant', slug: tenantSimpleLoginM[1], product: 'crm' }
    } else
    if (!isPlatformPath && tenantM) {
      context = { type: 'tenant', slug: tenantM[1], product: tenantM[2] }
    } else {
      context = { type: 'platform' }
    }
  }

  var isPlatform = context.type === 'platform'

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
  const sidebar = document.querySelector('.sidebar')
  if (sidebar) sidebar.style.display = 'none'

  const mainContent = document.querySelector('.main-content')
  if (mainContent) mainContent.style.marginLeft = '0'

  root.innerHTML =
    '<div style="display:flex;align-items:center;justify-content:center;min-height:100vh;background:' + (isPlatform ? '#f1f5f9' : loginBg) + ';">' +
      '<div class="card" style="max-width:420px;width:100%;">' +
        headerHtml +
        '<!-- Password login -->' +
        '<form id="loginForm" style="margin-top:24px;">' +
          '<input class="input" id="email" type="email" placeholder="Email" required />' +
          '<input class="input" id="password" type="password" placeholder="Password" required />' +
          '<label style="display:flex;align-items:center;gap:8px;margin-top:10px;font-size:13px;color:#64748b;cursor:pointer;">' +
            '<input type="checkbox" id="rememberMeCheck" style="width:15px;height:15px;cursor:pointer;" />' +
            'Remember me' +
          '</label>' +
          '<button class="button" style="width:100%;margin-top:16px;font-size:15px;">Login</button>' +
          '<div style="text-align:center;margin-top:12px;">' +
            '<a href="#" id="switchToOtp" style="font-size:13px;color:#0284c7;text-decoration:none;">Login with OTP instead &rarr;</a>' +
          '</div>' +
        '</form>' +
        '<!-- OTP login (hidden initially) -->' +
        '<div id="otpSection" style="display:none;margin-top:24px;">' +
          '<div id="otpStep1">' +
            '<input class="input" id="otpEmail" type="email" placeholder="Enter your email" required />' +
            '<label style="display:flex;align-items:center;gap:8px;margin-top:10px;font-size:13px;color:#64748b;cursor:pointer;">' +
              '<input type="checkbox" id="rememberMeOtpCheck" style="width:15px;height:15px;cursor:pointer;" />' +
              'Remember me' +
            '</label>' +
            '<button id="sendOtpBtn" class="button" style="width:100%;margin-top:12px;font-size:15px;">Send OTP</button>' +
          '</div>' +
          '<div id="otpStep2" style="display:none;">' +
            '<p id="otpSentMsg" style="text-align:center;color:#16a34a;font-size:13px;margin-bottom:12px;"></p>' +
            '<input class="input" id="otpCode" type="text" inputmode="numeric" maxlength="6" placeholder="Enter 6-digit OTP" style="letter-spacing:8px;font-size:20px;text-align:center;" required />' +
            '<button id="verifyOtpBtn" class="button" style="width:100%;margin-top:12px;font-size:15px;">Verify &amp; Login</button>' +
            '<div style="text-align:center;margin-top:8px;">' +
              '<a href="#" id="resendOtp" style="font-size:12px;color:#64748b;">Resend OTP</a>' +
            '</div>' +
          '</div>' +
          '<div style="text-align:center;margin-top:12px;">' +
            '<a href="#" id="switchToPassword" style="font-size:13px;color:#0284c7;text-decoration:none;">&larr; Back to password login</a>' +
          '</div>' +
        '</div>' +
        '<div id="loginError" style="color:#dc2626;text-align:center;margin-top:10px;font-size:13px;"></div>' +
      '</div>' +
    '</div>'

  // Password login
  document.getElementById('loginForm').addEventListener('submit', async function(e) {
    e.preventDefault()
    const email    = document.getElementById('email').value
    const password = document.getElementById('password').value
    const remember = document.getElementById('rememberMeCheck').checked
    const tenantSlug = (context && context.type === 'tenant') ? context.slug : null
    const errEl = document.getElementById('loginError')
    if (errEl) errEl.textContent = ''
    await login(email, password, remember, tenantSlug)
  })

  // Toggle to OTP
  document.getElementById('switchToOtp').addEventListener('click', function(e) {
    e.preventDefault()
    document.getElementById('loginForm').style.display = 'none'
    document.getElementById('otpSection').style.display = 'block'
    document.getElementById('loginError').textContent = ''
  })

  // Toggle back to password
  document.getElementById('switchToPassword').addEventListener('click', function(e) {
    e.preventDefault()
    document.getElementById('loginForm').style.display = 'block'
    document.getElementById('otpSection').style.display = 'none'
    document.getElementById('loginError').textContent = ''
  })

  async function sendOtp() {
    const emailVal = document.getElementById('otpEmail').value.trim()
    if (!emailVal) return
    const btn = document.getElementById('sendOtpBtn')
    btn.disabled = true
    btn.textContent = 'Sending...'
    document.getElementById('loginError').textContent = ''
    try {
      const res = await fetch(API_BASE + '/auth/send-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailVal }),
      })
      const data = await res.json()
      if (!res.ok) {
        document.getElementById('loginError').textContent = data.error || 'Failed to send OTP'
        btn.disabled = false
        btn.textContent = 'Send OTP'
        return
      }
      document.getElementById('otpStep1').style.display = 'none'
      document.getElementById('otpStep2').style.display = 'block'
      document.getElementById('otpSentMsg').textContent = 'OTP sent to ' + emailVal
      document.getElementById('otpCode').focus()
    } catch(err) {
      document.getElementById('loginError').textContent = 'Network error. Please try again.'
      btn.disabled = false
      btn.textContent = 'Send OTP'
    }
  }

  document.getElementById('sendOtpBtn').addEventListener('click', sendOtp)

  document.getElementById('resendOtp').addEventListener('click', function(e) {
    e.preventDefault()
    document.getElementById('otpStep1').style.display = 'block'
    document.getElementById('otpStep2').style.display = 'none'
    const btn = document.getElementById('sendOtpBtn')
    btn.disabled = false
    btn.textContent = 'Send OTP'
  })

  document.getElementById('verifyOtpBtn').addEventListener('click', async function() {
    const emailVal = document.getElementById('otpEmail').value.trim()
    const otpVal   = document.getElementById('otpCode').value.trim()
    const remember = document.getElementById('rememberMeOtpCheck').checked
    if (!otpVal || otpVal.length < 6) {
      document.getElementById('loginError').textContent = 'Please enter the 6-digit OTP'
      return
    }
    const btn = document.getElementById('verifyOtpBtn')
    btn.disabled = true
    btn.textContent = 'Verifying...'
    document.getElementById('loginError').textContent = ''
    try {
      const res = await fetch(API_BASE + '/auth/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: emailVal, otp: otpVal }),
      })
      const data = await res.json()
      if (!res.ok) {
        document.getElementById('loginError').textContent = data.error || 'Invalid OTP'
        btn.disabled = false
        btn.textContent = 'Verify & Login'
        return
      }
      authSetSession(data.token, data.user, remember)
      if (data.products) availableProducts = data.products
      authScheduleExpiry()
      if (loginRedirectPath && loginRedirectPath !== '/login' && !loginRedirectPath.endsWith('/login')) {
        history.pushState({}, '', loginRedirectPath)
        loginRedirectPath = ''
      }
      dispatch()
    } catch(err) {
      document.getElementById('loginError').textContent = 'Network error. Please try again.'
      btn.disabled = false
      btn.textContent = 'Verify & Login'
    }
  })
}
