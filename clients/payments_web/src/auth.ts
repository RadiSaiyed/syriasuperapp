export function getToken(): string | null {
  return localStorage.getItem('token')
}

export function setToken(tok: string) {
  localStorage.setItem('token', tok)
}

export function clearToken() {
  localStorage.removeItem('token')
}

