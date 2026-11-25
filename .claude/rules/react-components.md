---
paths:
  - "frontend/src/features/**/*.tsx"
  - "frontend/src/components/**/*.tsx"
---
- Every view handles loading, empty, error and success.
- Data only through hooks (TanStack Query or EventSource), never fetch in a component.
- Colours and spacing from the tokens in `@theme`, not scattered values.
- `cursor-pointer` on clickable elements.
- UI strings live in both dictionaries (`src/i18n/it.ts`, `src/i18n/en.ts`); the Italian ones use real accents.
