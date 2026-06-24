const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const ERROR_MESSAGES = {
  '未提供访问令牌': 'Please sign in to continue.',
  '访问令牌无效或已过期': 'Your session has expired. Please sign in again.',
  '账号已被禁用': 'This account has been disabled.',
  '用户名已存在': 'This username is already in use.',
  '用户名或密码错误': 'Invalid username or password.',
  '无权访问该资源': 'You do not have access to this resource.',
  '资源不存在': 'This resource could not be found.',
  '收藏记录不存在': 'This favorite could not be found.',
  'metainfo 必须是 JSON 对象': 'Metadata must be a JSON object.',
  'text 不能为空': 'A transcript is required.',
  '上传文件超过大小限制': 'The upload exceeds the file-size limit.',
  '不支持的音频 MIME 类型': 'This audio type is not supported.',
  '文件扩展名与音频 MIME 类型不匹配': 'The file extension does not match the audio type.',
  'WAV 文件头无效': 'The WAV file header is invalid.',
  '音频文件不存在': 'The audio file could not be found.',
  '必须提供音频文件': 'Please choose an audio file.',
  '请求参数校验失败': 'Please check the submitted fields.',
  '请求失败': 'The request could not be completed.',
  '数据库操作失败': 'A database error occurred.',
  '服务器内部错误': 'An internal server error occurred.',
  '不支持的 Range 请求': 'This audio range request is not supported.',
  '请求范围不满足': 'The requested audio range is not available.',
  'scope 必须为 dataset 或 mine': 'The resource scope is invalid.',
  '用户不存在': 'This user could not be found.',
  '需要管理员权限': 'Administrator access is required.',
}

function messageFor(message, fallback) {
  return ERROR_MESSAGES[message] || message || fallback
}

export async function api(path, { token, method = 'GET', body, headers = {} } = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body,
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(messageFor(payload?.message, `Request failed (${response.status})`))
  }
  return payload.data
}

export async function fetchAudio(path, token) {
  const response = await fetch(`${API_BASE}${path}`, { headers: { Authorization: `Bearer ${token}` } })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(messageFor(payload?.message, `Audio loading failed (${response.status})`))
  }
  return URL.createObjectURL(await response.blob())
}
