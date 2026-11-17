export function replaceSeparators(
  text: string,
  sources: readonly string[],
  target: string,
  { skipEmpty, deduplicate }: { skipEmpty: boolean; deduplicate: boolean },
): string {
  const delimiters = new Set(sources.flatMap(source => source === '\n' ? ['\r\n', '\n', '\r'] : [source]))
  delimiters.delete('')
  if (!delimiters.size) return text

  // Match longer delimiters first so a CRLF or custom sequence stays intact.
  const pattern = [...delimiters]
    .sort((a, b) => b.length - a.length)
    .map(delimiter => delimiter.replace(/[\\^$.*+?()[\]{}|]/g, '\\$&'))
    .join('|')

  let items = text.split(new RegExp(pattern))
  if (skipEmpty) items = items.filter(item => item !== '')
  if (deduplicate) items = [...new Set(items)]
  return items.join(target)
}
