import { computed, ref } from 'vue'
function read<T>(key: string, fallback: T): T {
  try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) as T : fallback } catch { return fallback }
}
const savedFavorites = read<unknown>('lee-toolbox:favorites', [])
const savedRecent = read<unknown>('lee-toolbox:recent', [])
export const favorites = ref<string[]>(Array.isArray(savedFavorites) ? savedFavorites.filter(v => typeof v === 'string') : [])
export const recent = ref<string[]>(Array.isArray(savedRecent) ? savedRecent.filter(v => typeof v === 'string') : [])
function save(key: string, value: unknown) { try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* Storage can be disabled; keep in-memory state. */ } }
export const favoriteCount = computed(() => favorites.value.length)
export function toggleFavorite(id: string) {
  favorites.value = favorites.value.includes(id) ? favorites.value.filter(item => item !== id) : [...favorites.value, id]
  save('lee-toolbox:favorites', favorites.value)
}
export function markRecent(id: string) {
  recent.value = [id, ...recent.value.filter(item => item !== id)].slice(0, 20)
  save('lee-toolbox:recent', recent.value)
}
