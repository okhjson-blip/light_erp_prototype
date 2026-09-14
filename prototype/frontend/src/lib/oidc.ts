// ERP 웹에서 Keycloak Authorization Code + PKCE 콜백을 처리한다.
const issuer = import.meta.env.VITE_OIDC_ISSUER ?? 'http://localhost:8081/realms/ax-enterprise'
const clientId = 'ax-erp-web'
const pendingKey = 'ax.erp.oidc.pending'

export class OidcError extends Error {}

function encodeBase64Url(bytes: Uint8Array) {
  let value = ''
  bytes.forEach((byte) => { value += String.fromCharCode(byte) })
  return btoa(value).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '')
}

function randomValue() {
  const bytes = new Uint8Array(32)
  crypto.getRandomValues(bytes)
  return encodeBase64Url(bytes)
}

async function createChallenge(verifier: string) {
  const bytes = new TextEncoder().encode(verifier)
  return encodeBase64Url(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)))
}

const attemptKey = 'ax.erp.oidc.attempted'
const interactiveKey = 'ax.erp.oidc.interactive'
const CALLBACK_PARAMS = ['code', 'state', 'session_state', 'iss', 'error', 'error_description']

/** redirect_uri는 fragment를 포함할 수 없다 (RFC 6749 §3.1.2). hash를 반드시 제거한다. */
function callbackUrl() {
  const url = new URL(window.location.href)
  for (const key of CALLBACK_PARAMS) url.searchParams.delete(key)
  url.hash = ''
  return url.toString()
}

function clearCallbackParameters() {
  const url = new URL(window.location.href)
  for (const key of CALLBACK_PARAMS) url.searchParams.delete(key)
  window.history.replaceState({}, document.title, `${url.pathname}${url.search}${url.hash}`)
}

/**
 * Keycloak이 돌려준 모든 error를 SSO 실패로 본다. login_required만 처리하면 interaction_required,
 * invalid_scope 등이 왔을 때 다시 silent 로그인으로 진입해 무한 리다이렉트가 된다.
 */
export function hasSsoError() {
  return new URLSearchParams(window.location.search).has('error')
}

/** Keycloak 세션만 없는 경우(대화형 로그인으로 해결 가능)인지 구분한다. */
export function isSessionMissingError() {
  const error = new URLSearchParams(window.location.search).get('error')
  return error === 'login_required' || error === 'interaction_required'
}

export function ssoErrorMessage() {
  const params = new URLSearchParams(window.location.search)
  const error = params.get('error')
  if (!error) return null
  if (isSessionMissingError()) return 'SSO 로그인이 필요합니다'
  return `SSO 로그인에 실패했습니다 (${error})`
}

export function clearSsoAttempt() {
  sessionStorage.removeItem(attemptKey)
  sessionStorage.removeItem(interactiveKey)
}

/** silent(prompt=none) / interactive(프롬프트 없음) 공통 authorize 리다이렉트. */
async function authorize(silent: boolean) {
  const verifier = randomValue()
  const state = randomValue()
  sessionStorage.setItem(pendingKey, JSON.stringify({ verifier, state }))
  const url = new URL(`${issuer}/protocol/openid-connect/auth`)
  const params: Record<string, string> = {
    client_id: clientId,
    redirect_uri: callbackUrl(),
    response_type: 'code',
    // openid는 필수다. 없으면 Keycloak 26 userinfo가 insufficient_scope(403)를 반환한다.
    scope: 'openid ax-claims',
    code_challenge: await createChallenge(verifier),
    code_challenge_method: 'S256',
    state,
  }
  if (silent) params.prompt = 'none'
  url.search = new URLSearchParams(params).toString()
  window.location.assign(url.toString())
}

export async function startSilentSsoLogin() {
  // 탭 단위 1회 가드. 실패 응답이 반복돼도 리다이렉트 루프에 빠지지 않는다.
  if (sessionStorage.getItem(attemptKey)) {
    throw new OidcError('SSO 로그인이 필요합니다')
  }
  sessionStorage.setItem(attemptKey, '1')
  await authorize(true)
}

/**
 * Keycloak 세션이 없을 때 곧바로 로그인 화면으로 보낸다.
 * 포털을 거치지 않고 ERP에서 바로 SSO 로그인이 가능해야 한다는 요구사항(2026-07-31).
 * silent와 별도 가드를 둬 리다이렉트 루프를 막는다.
 */
export async function startInteractiveSsoLogin() {
  if (sessionStorage.getItem(interactiveKey)) {
    throw new OidcError('SSO 로그인에 실패했습니다. All-in-One 포털에서 로그인 후 다시 시도하세요')
  }
  sessionStorage.setItem(interactiveKey, '1')
  await authorize(false)
}

export async function consumeSsoCallback() {
  const params = new URLSearchParams(window.location.search)
  const code = params.get('code')
  if (!code) return null
  const pending = JSON.parse(sessionStorage.getItem(pendingKey) || 'null')
  if (!pending || pending.state !== params.get('state')) throw new OidcError('SSO 로그인 상태를 확인할 수 없습니다')
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: clientId,
    redirect_uri: callbackUrl(),
    code,
    code_verifier: pending.verifier,
  })
  const response = await fetch(`${issuer}/protocol/openid-connect/token`, { method: 'POST', body })
  sessionStorage.removeItem(pendingKey)
  if (!response.ok) throw new OidcError('SSO 토큰을 발급하지 못했습니다')
  const token = await response.json() as { access_token?: string }
  if (!token.access_token) throw new OidcError('SSO access token이 없습니다')
  clearCallbackParameters()
  clearSsoAttempt()
  return token.access_token
}
