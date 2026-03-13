import zh from '../src/locales/zh.json' with { type: 'json' }
import en from '../src/locales/en.json' with { type: 'json' }
import ja from '../src/locales/ja.json' with { type: 'json' }
import ko from '../src/locales/ko.json' with { type: 'json' }
import fr from '../src/locales/fr.json' with { type: 'json' }
import de from '../src/locales/de.json' with { type: 'json' }

function collectKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([key, val]) => {
    const full = prefix ? `${prefix}.${key}` : key
    return val !== null && typeof val === 'object' && !Array.isArray(val)
      ? collectKeys(val as Record<string, unknown>, full)
      : [full]
  })
}

const zhKeys = new Set(collectKeys(zh as Record<string, unknown>))
const locales: Record<string, unknown> = { en, ja, ko, fr, de }
let failed = false

for (const [lang, data] of Object.entries(locales)) {
  const langKeys = new Set(collectKeys(data as Record<string, unknown>))
  const missing = [...zhKeys].filter(k => !langKeys.has(k))
  if (missing.length > 0) {
    console.error(`❌ ${lang} is missing ${missing.length} key(s):`)
    missing.forEach(k => console.error(`   - ${k}`))
    failed = true
  } else {
    console.log(`✅ ${lang}: all keys present`)
  }
}

if (failed) process.exit(1)
