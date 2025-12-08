# TellyAds UI Style Audit

**Date**: December 2024
**Status**: Issues Found

---

## Design System Overview

TellyAds uses a custom design system with the following core tokens:

### Colors (from tailwind.config.ts)
```
void: #0A0A0A (background)
signal: #FAFAFA (primary text)
antenna: #888888 (secondary text)
static: #1C1C1C (cards/surfaces)
transmission: #E63946 (accent/brand red)
```

### Typography
- **Display font**: Space Grotesk (`font-display`)
- **Mono font**: IBM Plex Mono (`font-mono`)

### Spacing
- Container: `max-w-7xl mx-auto px-6 lg:px-12`
- Section padding: `py-16` to `py-24`

### Components
- Header: Fixed, transparent → blur on scroll
- Footer: Standard bottom section
- Cards: `bg-static/30 border border-white/5 rounded`
- Badges: Custom `Badge` component with variants

---

## Pages Using Correct Design System

| Page | Uses Header | Uses Footer | Colors Correct | Layout Correct |
|------|-------------|-------------|----------------|----------------|
| `/` (Home) | ✅ | ✅ | ✅ | ✅ |
| `/browse` | ✅ | ✅ | ✅ | ✅ |
| `/search` | ✅ | ✅ | ✅ | ✅ |
| `/latest` | ✅ | ✅ | ✅ | ✅ |
| `/about` | ✅ | ✅ | ✅ | ✅ |
| `/ads/[external_id]` | ✅ | ✅ | ✅ | ✅ |

---

## ❌ Pages with Style Issues

### 1. `/brands` - CRITICAL

**File**: `frontend/app/brands/page.tsx`

**Issues**:
- Uses `bg-slate-50` instead of `bg-void`
- Uses `text-slate-900`, `text-slate-600` instead of `text-signal`, `text-antenna`
- Uses `bg-white` header instead of design system Header
- Uses `text-blue-600` accent instead of `text-transmission`
- Does not use shared Header/Footer components
- Different container width pattern

**Current (incorrect)**:
```tsx
<div className="min-h-screen bg-slate-50">
  <header className="bg-white border-b border-slate-200">
    ...
  </header>
</div>
```

**Should be**:
```tsx
<>
  <Header />
  <main className="min-h-screen pt-24 pb-16">
    <div className="max-w-7xl mx-auto px-6 lg:px-12">
      ...
    </div>
  </main>
  <Footer />
</>
```

---

### 2. `/advert/[brand]/[slug]` - MODERATE

**File**: `frontend/app/advert/[brand]/[slug]/page.tsx`

**Issues**:
- Uses `bg-gradient-to-b from-gray-950 to-black` instead of `bg-void`
- Uses `text-gray-400`, `text-gray-500` instead of `text-antenna`
- Uses `bg-gray-900/50` instead of `bg-static/30`
- Uses `text-red-400`, `text-red-300` instead of `text-transmission`
- Does not use shared Header/Footer components
- Uses `container mx-auto` instead of `max-w-7xl mx-auto px-6 lg:px-12`

**Styling differences**:
| Element | Current | Should Be |
|---------|---------|-----------|
| Background | `from-gray-950 to-black` | `bg-void` |
| Secondary text | `text-gray-400` | `text-antenna` |
| Cards | `bg-gray-900/50` | `bg-static/30` |
| Accent | `text-red-400` | `text-transmission` |
| Border | `border-red-500/10` | `border-white/5` |

---

### 3. `/random` - LOW

**File**: `frontend/app/random/page.tsx`

**Issues**:
- No visual output (redirect-only page)
- No Header/Footer (acceptable for redirect)

**Status**: Acceptable - this is a server-side redirect page with no visual output

---

### 4. `/admin/*` - ACCEPTABLE

**Files**: `frontend/app/admin/**/*.tsx`

**Status**: Admin pages use a distinct but consistent style. This is acceptable as they are private pages not meant for public users.

---

## Shared Layout Pattern

Most pages follow this structure:

```tsx
export default function PageName() {
  return (
    <>
      <Header />
      <main className="min-h-screen pt-24 pb-16">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          {/* Page content */}
        </div>
      </main>
      <Footer />
    </>
  );
}
```

**Recommendation**: Create a `PageShell` component to enforce this pattern:

```tsx
// components/layout/PageShell.tsx
export function PageShell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Header />
      <main className="min-h-screen pt-24 pb-16">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          {children}
        </div>
      </main>
      <Footer />
    </>
  );
}
```

---

## Disallowed Patterns (grep audit)

### Inline Styles
```bash
grep -r "style=" frontend/app --include="*.tsx" | grep -v "// style"
```
**Result**: No inline style attributes found ✅

### One-off Color Classes
```bash
grep -rE "bg-slate|bg-gray|text-slate|text-gray" frontend/app --include="*.tsx"
```
**Result**: Found in `/brands/page.tsx` and `/advert/[brand]/[slug]/page.tsx` ❌

### Non-standard Container Widths
```bash
grep -rE "container mx-auto|max-w-6xl|max-w-5xl" frontend/app --include="*.tsx"
```
**Result**: Found `container mx-auto` in `/advert/[brand]/[slug]/page.tsx` ❌

---

## Required Fixes

### Priority 1 (Critical)

1. **Refactor `/brands/page.tsx`**
   - Import and use `Header`, `Footer` from `@/components/layout`
   - Change background to `bg-void`
   - Change text colors to design system tokens
   - Use proper container pattern

2. **Refactor `/advert/[brand]/[slug]/page.tsx`**
   - Import and use `Header`, `Footer` from `@/components/layout`
   - Change background to `bg-void`
   - Replace gray/red palette with design system tokens
   - Use `max-w-7xl mx-auto px-6 lg:px-12` container

### Priority 2 (Important)

3. **Create PageShell component**
   - Encapsulates Header + main + Footer pattern
   - Enforces consistent spacing
   - Reduces code duplication

---

## Definition of Done

- [ ] All public pages use `Header` and `Footer` components
- [ ] All pages use `bg-void` for background
- [ ] All pages use `text-signal` for primary text
- [ ] All pages use `text-antenna` for secondary text
- [ ] All accent colors use `text-transmission`
- [ ] All cards use `bg-static/30 border border-white/5`
- [ ] All containers use `max-w-7xl mx-auto px-6 lg:px-12`
- [ ] No inline styles
- [ ] No gray-* or slate-* color classes in public pages

---

*Last updated: December 2024*
