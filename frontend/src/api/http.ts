import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'

const UNSAFE_METHODS = new Set(['post', 'put', 'patch', 'delete'])
const csrfCookieName = import.meta.env.VITE_CSRF_COOKIE_NAME || 'agenticops_csrf'

function readCookie(name: string): string | undefined {
  const prefix = `${encodeURIComponent(name)}=`
  const item = document.cookie.split('; ').find((value) => value.startsWith(prefix))
  return item ? decodeURIComponent(item.slice(prefix.length)) : undefined
}

function attachCsrf(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  config.withCredentials = true
  if (UNSAFE_METHODS.has((config.method || 'get').toLowerCase())) {
    const token = readCookie(csrfCookieName)
    if (token) config.headers.set('X-CSRF-Token', token)
  }
  return config
}

export function configureAxios(instance: AxiosInstance): AxiosInstance {
  instance.defaults.withCredentials = true
  instance.interceptors.request.use(attachCsrf)
  instance.interceptors.response.use(
    (response) => response,
    (error: unknown) => {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        window.dispatchEvent(new CustomEvent('auth:unauthorized'))
      }
      return Promise.reject(error)
    }
  )
  return instance
}

configureAxios(axios)

export default axios
