import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:10223'

export const http = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

let authStoreGetter = null
let uiStoreGetter = null
let routerGetter = null

export function registerApiContext({ getAuthStore, getUiStore, getRouter }) {
  authStoreGetter = getAuthStore
  uiStoreGetter = getUiStore
  routerGetter = getRouter
}

http.interceptors.request.use((config) => {
  const authStore = authStoreGetter?.()
  if (authStore?.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const uiStore = uiStoreGetter?.()
    const authStore = authStoreGetter?.()
    const router = routerGetter?.()

    if (error.response?.status === 401 && authStore) {
      authStore.logoutLocal()
      router?.push('/login')
    }

    const detail = error.response?.data?.error?.message || error.response?.data?.detail || error.message
    uiStore?.setError(typeof detail === 'string' ? detail : '요청 처리 중 오류가 발생했습니다.')
    return Promise.reject(error)
  },
)

export async function apiGet(url, config = {}) {
  const { data } = await http.get(url, config)
  return data.data
}

export async function apiPost(url, payload = {}, config = {}) {
  const { data } = await http.post(url, payload, config)
  return data.data
}

export async function apiPut(url, payload = {}, config = {}) {
  const { data } = await http.put(url, payload, config)
  return data.data
}

export async function apiDelete(url, config = {}) {
  const response = await http.delete(url, config)
  return response.data?.data ?? null
}

export async function downloadFile(url, filenameHint = 'download', config = {}) {
  const method = (config.method || 'get').toLowerCase()
  const requestConfig = {
    ...config,
    method,
    responseType: 'blob',
  }
  const response = method === 'get'
    ? await http.get(url, requestConfig)
    : await http.request({ url, ...requestConfig })
  const blobUrl = window.URL.createObjectURL(response.data)
  const link = document.createElement('a')
  const disposition = response.headers['content-disposition']
  const fileNameUtfMatch = disposition?.match(/filename\*=UTF-8''([^;]+)/i)
  const fileNameMatch = disposition?.match(/filename="?([^";]+)"?/i)
  const resolvedFileName = fileNameUtfMatch?.[1]
    ? decodeURIComponent(fileNameUtfMatch[1])
    : fileNameMatch?.[1]
  link.href = blobUrl
  link.download = resolvedFileName || filenameHint
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(blobUrl)
}

export { API_BASE_URL }
