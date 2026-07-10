import { ref } from 'vue'

export type ThemeKey = 'orange' | 'pink' | 'ocean' | 'mint' | 'grape' | 'lemon'

export interface ThemeOption {
  key: ThemeKey
  label: string
  emoji: string
  preview: string
}

interface ThemePalette {
  brand: [string, string, string, string, string, string, string, string]
  shadowPop: string
  themeColor: string
  shellGradient: string
  innerGradient: string
}

const BRAND_KEYS = ['50', '100', '200', '300', '400', '500', '600', '700'] as const

const THEME_PRESETS: Record<ThemeKey, ThemePalette> = {
  orange: {
    brand: ['255 248 243', '255 237 217', '255 217 179', '255 191 128', '255 159 82', '255 127 42', '240 101 21', '208 79 10'],
    shadowPop: '0 10px 28px -8px rgba(240, 101, 21, 0.38)',
    themeColor: '#ffedd9',
    shellGradient: 'linear-gradient(to bottom right, rgb(var(--brand-100)), rgba(255, 201, 51, 0.25), rgba(255, 77, 148, 0.2))',
    innerGradient:
      'radial-gradient(circle at 12% 8%, rgba(255, 201, 51, 0.42), transparent 44%), radial-gradient(circle at 88% 10%, rgba(255, 77, 148, 0.32), transparent 40%), radial-gradient(circle at 72% 78%, rgba(56, 189, 248, 0.28), transparent 38%), radial-gradient(circle at 18% 88%, rgba(46, 204, 154, 0.24), transparent 42%)',
  },
  pink: {
    brand: ['255 245 249', '255 232 242', '255 208 227', '255 176 207', '255 133 184', '255 92 160', '236 64 137', '208 40 112'],
    shadowPop: '0 10px 28px -8px rgba(236, 64, 137, 0.38)',
    themeColor: '#ffe8f2',
    shellGradient: 'linear-gradient(to bottom right, rgb(var(--brand-100)), rgb(var(--brand-200) / 0.5), rgb(var(--brand-300) / 0.3))',
    innerGradient:
      'radial-gradient(circle at 12% 8%, rgba(255, 140, 190, 0.45), transparent 44%), radial-gradient(circle at 88% 10%, rgba(255, 92, 160, 0.38), transparent 40%), radial-gradient(circle at 72% 78%, rgba(255, 176, 207, 0.35), transparent 38%), radial-gradient(circle at 18% 88%, rgba(236, 64, 137, 0.28), transparent 42%)',
  },
  ocean: {
    brand: ['240 249 255', '224 242 254', '186 230 253', '125 211 252', '56 189 248', '14 165 233', '2 132 199', '3 105 161'],
    shadowPop: '0 10px 28px -8px rgba(2, 132, 199, 0.38)',
    themeColor: '#e0f2fe',
    shellGradient: 'linear-gradient(to bottom right, rgb(var(--brand-100)), rgb(var(--brand-200) / 0.6), rgb(var(--brand-300) / 0.35))',
    innerGradient:
      'radial-gradient(circle at 12% 8%, rgba(56, 189, 248, 0.4), transparent 44%), radial-gradient(circle at 88% 10%, rgba(14, 165, 233, 0.32), transparent 40%), radial-gradient(circle at 72% 78%, rgba(125, 211, 252, 0.3), transparent 38%), radial-gradient(circle at 18% 88%, rgba(2, 132, 199, 0.22), transparent 42%)',
  },
  mint: {
    brand: ['240 253 250', '204 251 241', '153 246 228', '94 234 212', '45 212 191', '20 184 166', '13 148 136', '15 118 110'],
    shadowPop: '0 10px 28px -8px rgba(13, 148, 136, 0.38)',
    themeColor: '#ccfbf1',
    shellGradient: 'linear-gradient(to bottom right, rgb(var(--brand-100)), rgb(var(--brand-200) / 0.55), rgb(var(--brand-300) / 0.3))',
    innerGradient:
      'radial-gradient(circle at 12% 8%, rgba(45, 212, 191, 0.4), transparent 44%), radial-gradient(circle at 88% 10%, rgba(20, 184, 166, 0.32), transparent 40%), radial-gradient(circle at 72% 78%, rgba(94, 234, 212, 0.28), transparent 38%), radial-gradient(circle at 18% 88%, rgba(13, 148, 136, 0.22), transparent 42%)',
  },
  grape: {
    brand: ['250 245 255', '243 232 255', '233 213 255', '216 180 254', '192 132 252', '168 85 247', '147 51 234', '126 34 206'],
    shadowPop: '0 10px 28px -8px rgba(147, 51, 234, 0.38)',
    themeColor: '#f3e8ff',
    shellGradient: 'linear-gradient(to bottom right, rgb(var(--brand-100)), rgb(var(--brand-200) / 0.55), rgb(var(--brand-300) / 0.32))',
    innerGradient:
      'radial-gradient(circle at 12% 8%, rgba(192, 132, 252, 0.42), transparent 44%), radial-gradient(circle at 88% 10%, rgba(168, 85, 247, 0.34), transparent 40%), radial-gradient(circle at 72% 78%, rgba(216, 180, 254, 0.3), transparent 38%), radial-gradient(circle at 18% 88%, rgba(147, 51, 234, 0.24), transparent 42%)',
  },
  lemon: {
    brand: ['254 252 232', '254 249 195', '254 240 138', '253 224 71', '250 204 21', '234 179 8', '202 138 4', '161 98 7'],
    shadowPop: '0 10px 28px -8px rgba(202, 138, 4, 0.38)',
    themeColor: '#fef9c3',
    shellGradient: 'linear-gradient(to bottom right, rgb(var(--brand-100)), rgb(var(--brand-200) / 0.5), rgb(var(--brand-300) / 0.28))',
    innerGradient:
      'radial-gradient(circle at 12% 8%, rgba(250, 204, 21, 0.42), transparent 44%), radial-gradient(circle at 88% 10%, rgba(234, 179, 8, 0.32), transparent 40%), radial-gradient(circle at 72% 78%, rgba(253, 224, 71, 0.3), transparent 38%), radial-gradient(circle at 18% 88%, rgba(202, 138, 4, 0.22), transparent 42%)',
  },
}

export const COLOR_THEMES: ThemeOption[] = [
  { key: 'orange', label: '暖橙', emoji: '🍊', preview: '#ff7f2a' },
  { key: 'pink', label: '樱花粉', emoji: '🌸', preview: '#ff5ca0' },
  { key: 'ocean', label: '海洋蓝', emoji: '🌊', preview: '#0ea5e9' },
  { key: 'mint', label: '薄荷绿', emoji: '🌿', preview: '#14b8a6' },
  { key: 'grape', label: '葡萄紫', emoji: '🍇', preview: '#a855f7' },
  { key: 'lemon', label: '柠檬黄', emoji: '🍋', preview: '#eab308' },
]

const THEME_KEY = 'jumprope_color_theme'

export const colorTheme = ref<ThemeKey>('orange')

function isThemeKey(raw: string): raw is ThemeKey {
  return raw in THEME_PRESETS
}

export function getStoredColorTheme(): ThemeKey | null {
  if (typeof localStorage === 'undefined') return null
  const stored = localStorage.getItem(THEME_KEY)
  return stored && isThemeKey(stored) ? stored : null
}

export function getColorTheme(): ThemeKey {
  return getStoredColorTheme() ?? 'orange'
}

export function applyColorTheme(key?: ThemeKey): void {
  if (typeof document === 'undefined') return
  const theme = key ?? getColorTheme()
  const palette = THEME_PRESETS[theme]
  const root = document.documentElement

  colorTheme.value = theme
  root.dataset.theme = theme
  BRAND_KEYS.forEach((suffix, i) => {
    root.style.setProperty(`--brand-${suffix}`, palette.brand[i])
  })
  root.style.setProperty('--shadow-pop', palette.shadowPop)
  root.style.setProperty('--shell-gradient', palette.shellGradient)
  root.style.setProperty('--shell-inner-gradient', palette.innerGradient)

  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.setAttribute('content', palette.themeColor)
}

export function setColorTheme(key: ThemeKey): void {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(THEME_KEY, key)
  }
  applyColorTheme(key)
}
