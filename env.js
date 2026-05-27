// Runtime environment configuration for static frontend (no build step).
// Override by setting window.__SOCIOMONKEY_ENV__ before this file loads.
(function () {
	var runtime = window.__SOCIOMONKEY_ENV__ || {}
	var host = (window.location && window.location.hostname) || ''
	var isLocal = host === 'localhost' || host === '127.0.0.1'

	var defaultApiBase = isLocal
		? 'http://127.0.0.1:5002/api'
		: 'https://sociomonkey-backend-production.up.railway.app/api'

	var apiBase = runtime.API_BASE || defaultApiBase

	window.SOCIOMONKEY_ENV = {
		ENV: runtime.ENV || (isLocal ? 'development' : 'production'),
		API_BASE: apiBase,
	}

	// Preserve backward compatibility with existing code paths.
	window.API_BASE = apiBase
})()
