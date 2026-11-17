const MAX_INPUT = 500_000
const MAX_OUTPUT = 2_000_000
const MAX_HIGHLIGHT_TOKENS = 12_000
const JSON_TOKEN = /"[^"\\]*(?:\\.[^"\\]*)*"|[{}\[\],:]|[^"{}\[\],:\s]+/g

export function formatJson(source: string, indentation: 0 | 2 | 4): string {
  if (source.length > MAX_INPUT) throw new Error('JSON 超过 50 万字符，请分段处理。')
  try {
    // Validate with the native parser, then keep the original tokens for output.
    JSON.parse(source)
  } catch (cause) {
    const detail = cause instanceof SyntaxError ? ` ${cause.message}` : ''
    throw new Error(`JSON 格式无效。${detail}`)
  }

  const tokens = source.match(JSON_TOKEN) ?? []
  if (indentation === 0) return tokens.join('')

  const output: string[] = []
  let outputSize = 0
  let depth = 0

  function append(text: string) {
    outputSize += text.length
    if (outputSize > MAX_OUTPUT) throw new Error('格式化结果过长，请减小缩进或选择压缩。')
    output.push(text)
  }

  function newline() {
    append(`\n${' '.repeat(depth * indentation)}`)
  }

  for (const [index, token] of tokens.entries()) {
    const previous = tokens[index - 1]
    const followsOpening = previous === '{' || previous === '['
    if (token === '}' || token === ']') {
      depth--
      if (!followsOpening) newline()
    } else if (followsOpening || previous === ',') {
      newline()
    }

    append(token)
    if (token === ':') append(' ')
    if (token === '{' || token === '[') depth++
  }
  return output.join('')
}

type TokenKind = 'key' | 'string' | 'number' | 'boolean' | 'null' | 'plain'
interface PreviewToken { text: string; kind: TokenKind }
interface PreviewLine {
  index: number
  tokens: PreviewToken[]
  fold?: { end: number; closing: string; label: '对象' | '数组' }
}

function tokenKind(text: string, followingCharacter: string | undefined): TokenKind {
  if (text.startsWith('"')) return followingCharacter === ':' ? 'key' : 'string'
  if (text === 'true' || text === 'false') return 'boolean'
  if (text === 'null') return 'null'
  if (/^-?\d/.test(text)) return 'number'
  return 'plain'
}

/** Highlight the formatted source without reserializing any values. */
export function buildJsonPreview(output: string): PreviewLine[] | null {
  if (!output) return []
  const lines: PreviewLine[] = []
  const openings: PreviewLine[] = []
  let tokenCount = 0

  for (const [index, text] of output.split('\n', MAX_HIGHLIGHT_TOKENS + 1).entries()) {
    const tokens: PreviewToken[] = []
    let offset = 0
    for (const match of text.matchAll(JSON_TOKEN)) {
      if (++tokenCount > MAX_HIGHLIGHT_TOKENS) return null
      const start = match.index ?? 0
      if (start > offset) tokens.push({ text: text.slice(offset, start), kind: 'plain' })
      const value = match[0]
      offset = start + value.length
      tokens.push({ text: value, kind: tokenKind(value, text[offset]) })
    }

    // The formatter puts each non-empty container's opening and closing on separate lines.
    const line = { index, tokens }
    const closing = text.trimStart()
    if (closing.startsWith('}') || closing.startsWith(']')) {
      const opening = openings.pop()
      if (opening) opening.fold = { end: index, closing, label: closing[0] === '}' ? '对象' : '数组' }
    }
    const last = tokens.at(-1)?.text
    if (last === '{' || last === '[') openings.push(line)
    lines.push(line)
  }
  return lines
}
