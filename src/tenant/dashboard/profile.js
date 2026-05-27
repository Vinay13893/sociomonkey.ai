// MY PROFILE
// ============================================================================

async function renderMyProfile() {
  const content = document.getElementById('content')
  content.innerHTML = `
    <div class="card" style="max-width:600px;">
      <h2>My Profile & Password</h2>
      
      <div style="background:#f8fafc;padding:16px;border-radius:10px;margin-bottom:24px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;font-size:14px;">
          <div>
            <span style="color:#64748b;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Name</span>
            <div style="color:#1e293b;font-weight:500;margin-top:4px;">${escape(user.name)}</div>
          </div>
          <div>
            <span style="color:#64748b;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Email</span>
            <div style="color:#1e293b;font-weight:500;margin-top:4px;">${escape(user.email)}</div>
          </div>
          <div>
            <span style="color:#64748b;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Role</span>
            <div style="color:#1e293b;font-weight:500;margin-top:4px;">${getRoleDisplay(user.role)}</div>
          </div>
          <div>
            <span style="color:#64748b;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;">Status</span>
            <div style="color:#059669;font-weight:500;margin-top:4px;">âœ“ Active</div>
          </div>
        </div>
      </div>

      <form id="passwordForm">
        <div style="border-top:1px solid #e2e8f0;padding-top:20px;">
          <h3 style="margin:0 0 16px;font-size:1.05rem;color:#1e293b;font-weight:600;">Change Password</h3>
          
          <div style="margin-bottom:14px;">
            <label style="display:block;font-size:13px;font-weight:600;color:#475569;margin-bottom:6px;">Current Password *</label>
            <input class="input" id="currentPassword" placeholder="Enter your current password" type="password" required />
          </div>
          
          <div style="margin-bottom:14px;">
            <label style="display:block;font-size:13px;font-weight:600;color:#475569;margin-bottom:6px;">New Password *</label>
            <input class="input" id="newPassword" placeholder="Enter new password (min. 8 characters)" type="password" required minlength="8" />
            <p style="font-size:12px;color:#94a3b8;margin-top:4px;">Use uppercase, lowercase, numbers, and special characters for security</p>
          </div>
          
          <div style="margin-bottom:20px;">
            <label style="display:block;font-size:13px;font-weight:600;color:#475569;margin-bottom:6px;">Confirm New Password *</label>
            <input class="input" id="confirmPassword" placeholder="Confirm your new password" type="password" required />
          </div>
          
          <div style="display:flex;gap:10px;">
            <button type="submit" class="button">ðŸ” Update Password</button>
            <button type="button" class="button secondary" onclick="renderApp(); showContent()">Cancel</button>
          </div>
        </div>
      </form>
    </div>
  `
  
  document.getElementById('passwordForm').addEventListener('submit', async e => {
    e.preventDefault()
    const currentPassword = document.getElementById('currentPassword').value
    const newPassword = document.getElementById('newPassword').value
    const confirmPassword = document.getElementById('confirmPassword').value
    
    if (newPassword !== confirmPassword) {
      showToast('New passwords do not match', 'warning')
      return
    }
    
    if (newPassword.length < 8) {
      showToast('New password must be at least 8 characters', 'warning')
      return
    }
    
    const res = await fetch(`${API_BASE}/auth/change-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
    })
    
    const data = await res.json()
    if (res.ok) {
      showToast('Password updated successfully! Logging you out…', 'success')
      setTimeout(function () {
        token = ''
        user = null
        localStorage.removeItem('lms_token')
        sessionStorage.removeItem('lms_token')
        if (typeof dispatch === 'function') dispatch()
        else window.location.reload()
      }, 2000)
    } else {
      showToast(data.error || 'Error updating password', 'error')
    }
  })
}

// ============================================================================
