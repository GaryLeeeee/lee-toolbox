import { diffLines } from 'diff'

const MAX_CHARACTERS = 200_000
const MAX_LINES = 4_000

interface DiffRow {
  kind: 'added' | 'removed' | 'unchanged'
  before: number | null
  after: number | null
  text: string
  endsWithNewline: boolean
}

function lineCount(text: string) {
  return text.split('\n', MAX_LINES + 2).length - Number(text.endsWith('\n'))
}

export function compareText(original: string, modified: string) {
  const before = original.replace(/\r\n?/g, '\n')
  const after = modified.replace(/\r\n?/g, '\n')
  if ([before, after].some(text => text.length > MAX_CHARACTERS || lineCount(text) > MAX_LINES)) {
    throw new Error('每段文本最多支持 20 万字符和 4,000 行，请分段对比。')
  }

  const changes = diffLines(before, after, { oneChangePerToken: true, timeout: 400 })
  if (!changes) throw new Error('差异较多，请缩小文本范围后重试。')

  const rows: DiffRow[] = []
  let beforeLine = 1
  let afterLine = 1
  let added = 0
  let removed = 0
  for (const change of changes) {
    if (!change.count) continue
    if (change.added) added++
    if (change.removed) removed++
    const endsWithNewline = change.value.endsWith('\n')
    rows.push({
      kind: change.added ? 'added' : change.removed ? 'removed' : 'unchanged',
      before: change.added ? null : beforeLine++,
      after: change.removed ? null : afterLine++,
      text: endsWithNewline ? change.value.slice(0, -1) : change.value,
      endsWithNewline,
    })
  }
  return { rows, added, removed }
}
