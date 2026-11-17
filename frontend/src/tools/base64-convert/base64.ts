const MAX_BYTES = 1_000_000
const TOO_LARGE = '文本超过 1 MB，请分段处理。'

export function encodeBase64(source: string): string {
  if (source.length > MAX_BYTES) throw new Error(TOO_LARGE)
  const bytes = new TextEncoder().encode(source)
  if (bytes.length > MAX_BYTES) throw new Error(TOO_LARGE)

  const parts: string[] = []
  for (let offset = 0; offset < bytes.length; offset += 8192) {
    parts.push(String.fromCharCode(...bytes.subarray(offset, offset + 8192)))
  }
  return btoa(parts.join(''))
}

export function decodeBase64(source: string): string {
  if (source.length > MAX_BYTES * 2) throw new Error(TOO_LARGE)
  const normalized = source.replaceAll('-', '+').replaceAll('_', '/')
  let binary: string
  try {
    binary = atob(normalized)
  } catch {
    throw new Error('Base64 格式无效，请检查字符和末尾的 = 填充。')
  }
  if (binary.length > MAX_BYTES) throw new Error(TOO_LARGE)
  if (!binary) throw new Error('请粘贴要解码的 Base64。')

  const bytes = Uint8Array.from(binary, char => char.charCodeAt(0))
  try {
    return new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes)
  } catch {
    throw new Error('解码结果不是有效的 UTF-8 文本。')
  }
}
