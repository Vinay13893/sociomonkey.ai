import json
import random
import time
import urllib.parse
import urllib.request
from datetime import datetime
from urllib.error import HTTPError, URLError

GRAPH_BASE = 'https://graph.facebook.com/v25.0'


_ENDPOINTS = [
    {
        'key': 'me_adaccounts',
        'template': '/me/adaccounts',
        'params': {'fields': 'id,name,account_status', 'limit': '25'},
    },
    {
        'key': 'act_campaigns',
        'template': '/act_{ad_account_id}/campaigns',
        'params': {'fields': 'id,name,status', 'limit': '25'},
    },
    {
        'key': 'act_insights',
        'template': '/act_{ad_account_id}/insights',
        'params': {'fields': 'impressions,clicks,spend', 'date_preset': 'last_7d', 'limit': '10'},
    },
    {
        'key': 'page_leadgen_forms',
        'template': '/{page_id}/leadgen_forms',
        'params': {'fields': 'id,name,status', 'limit': '25'},
    },
    {
        'key': 'me_accounts',
        'template': '/me/accounts',
        'params': {'fields': 'id,name,tasks', 'limit': '25'},
    },
]

_RATE_LIMIT_ERROR_CODES = {4, 17, 32, 613}


def now_iso():
    return datetime.utcnow().isoformat() + 'Z'


def _normalize_ad_account_id(ad_account_id):
    raw = str(ad_account_id or '').strip()
    if raw.lower().startswith('act_'):
        return raw[4:]
    return raw


def build_initial_state(target_success_calls=500):
    return {
        'started_at': now_iso(),
        'updated_at': now_iso(),
        'target_success_calls': int(target_success_calls or 500),
        'total_calls': 0,
        'success_calls': 0,
        'failed_calls': 0,
        'counted_calls_toward_testing': 0,
        'status_codes': {},
        'endpoint_stats': {},
        'recent_results': [],
        'last_error': '',
        'goal_met': False,
        'success_rate': 0.0,
    }


def _build_graph_url(endpoint_template, params, ad_account_id, page_id, access_token):
    path = endpoint_template.format(
        ad_account_id=_normalize_ad_account_id(ad_account_id),
        page_id=str(page_id or '').strip(),
    )
    query = dict(params or {})
    query['access_token'] = access_token
    return GRAPH_BASE + path + '?' + urllib.parse.urlencode(query)


def _is_rate_limited(error_code, status):
    if status == 429:
        return True
    if error_code in _RATE_LIMIT_ERROR_CODES:
        return True
    return False


def _graph_call(url, endpoint_key, timeout_s=20):
    status = 0
    payload = None
    error = {}
    raw_body = ''

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SocioMonkey-MetaTierTest/1.0'})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = int(resp.getcode() or 0)
            body = resp.read()
        raw_body = body.decode('utf-8', errors='replace')
        payload = json.loads(raw_body)
    except HTTPError as exc:
        status = int(exc.code or 0)
        body = exc.read() if hasattr(exc, 'read') else b''
        raw_body = body.decode('utf-8', errors='replace')
        try:
            payload = json.loads(raw_body) if raw_body else {}
        except Exception:
            payload = {'error': {'message': raw_body or str(exc), 'type': 'HTTPError'}}
    except URLError as exc:
        status = 0
        payload = {'error': {'message': str(exc), 'type': 'URLError'}}
    except Exception as exc:
        status = 0
        payload = {'error': {'message': str(exc), 'type': 'Exception'}}

    if isinstance(payload, dict) and isinstance(payload.get('error'), dict):
        err = payload.get('error') or {}
        error = {
            'code': err.get('code'),
            'error_subcode': err.get('error_subcode'),
            'message': err.get('message') or '',
            'type': err.get('type') or '',
        }
    else:
        error = {'code': None, 'error_subcode': None, 'message': '', 'type': ''}

    success = 200 <= status < 300 and not error.get('message')

    return {
        'timestamp': now_iso(),
        'endpoint_key': endpoint_key,
        'status': status,
        'success': success,
        'error': error,
        'raw_response': payload if isinstance(payload, (dict, list)) else {'raw': raw_body},
    }


def _update_state(state, result):
    status = str(result.get('status', 0))
    endpoint_key = result.get('endpoint_key') or 'unknown'
    success = bool(result.get('success'))

    state['total_calls'] = int(state.get('total_calls', 0)) + 1
    if success:
        state['success_calls'] = int(state.get('success_calls', 0)) + 1
        state['counted_calls_toward_testing'] = int(state.get('counted_calls_toward_testing', 0)) + 1
    else:
        state['failed_calls'] = int(state.get('failed_calls', 0)) + 1

    codes = state.setdefault('status_codes', {})
    codes[status] = int(codes.get(status, 0)) + 1

    endpoint_stats = state.setdefault('endpoint_stats', {})
    ep = endpoint_stats.setdefault(endpoint_key, {'calls': 0, 'success': 0, 'status_codes': {}})
    ep['calls'] = int(ep.get('calls', 0)) + 1
    if success:
        ep['success'] = int(ep.get('success', 0)) + 1
    ep_codes = ep.setdefault('status_codes', {})
    ep_codes[status] = int(ep_codes.get(status, 0)) + 1

    results = state.setdefault('recent_results', [])
    results.append(result)
    if len(results) > 50:
        del results[:-50]

    total_calls = max(1, int(state.get('total_calls', 0)))
    success_calls = int(state.get('success_calls', 0))
    state['success_rate'] = round((success_calls * 100.0) / total_calls, 2)
    state['goal_met'] = success_calls >= int(state.get('target_success_calls', 500))
    state['updated_at'] = now_iso()

    if not success:
        err = result.get('error') or {}
        state['last_error'] = err.get('message') or 'Request failed'


def run_batch(config, state, access_token):
    ad_account_id = str((config or {}).get('ad_account_id') or '').strip()
    page_id = str((config or {}).get('page_id') or '').strip()
    batch_size = int((config or {}).get('batch_size') or 15)
    min_delay_ms = int((config or {}).get('min_delay_ms') or 350)
    max_delay_ms = int((config or {}).get('max_delay_ms') or 900)

    if batch_size < 1:
        batch_size = 1
    if batch_size > 100:
        batch_size = 100
    if min_delay_ms < 50:
        min_delay_ms = 50
    if max_delay_ms < min_delay_ms:
        max_delay_ms = min_delay_ms

    if not access_token:
        raise ValueError('access_token is required')
    if not ad_account_id:
        raise ValueError('ad_account_id is required')
    if not page_id:
        raise ValueError('page_id is required')

    state = dict(state or {})
    state.setdefault('target_success_calls', int((config or {}).get('target_success_calls') or 500))

    results = []
    retry_streak = 0

    for i in range(batch_size):
        total_before = int(state.get('total_calls', 0))
        ep = _ENDPOINTS[total_before % len(_ENDPOINTS)]

        url = _build_graph_url(
            ep['template'],
            ep['params'],
            ad_account_id=ad_account_id,
            page_id=page_id,
            access_token=access_token,
        )
        result = _graph_call(url, endpoint_key=ep['key'])
        results.append(result)
        _update_state(state, result)

        err = result.get('error') or {}
        is_rl = _is_rate_limited(err.get('code'), result.get('status'))
        if is_rl:
            retry_streak += 1
            backoff = min(6.0, (2 ** min(retry_streak, 4)) * 0.25)
            time.sleep(backoff)
        else:
            retry_streak = 0

        delay_ms = random.randint(min_delay_ms, max_delay_ms)
        time.sleep(delay_ms / 1000.0)

        if state.get('goal_met'):
            break

    dashboard = compute_dashboard(state)
    return state, results, dashboard


def compute_dashboard(state):
    total = int((state or {}).get('total_calls', 0))
    success = int((state or {}).get('success_calls', 0))
    counted = int((state or {}).get('counted_calls_toward_testing', 0))
    target = int((state or {}).get('target_success_calls', 500))
    success_rate = round((success * 100.0) / total, 2) if total else 0.0
    return {
        'total_marketing_api_calls': total,
        'success_percent': success_rate,
        'calls_counted_toward_meta_testing': counted,
        'target_success_calls': target,
        'remaining_success_calls_to_target': max(0, target - success),
        'goal_met': success >= target,
    }
