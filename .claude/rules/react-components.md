---
paths:
  - "frontend/src/features/**/*.tsx"
  - "frontend/src/components/**/*.tsx"
---
- Ogni vista gestisce loading, empty, error e success.
- Dati solo via hook (TanStack Query o EventSource), mai fetch nel componente.
- Colori e spaziature dai token in `@theme`, non valori sparsi.
- `cursor-pointer` sugli elementi cliccabili.
- Testi UI in italiano con gli accenti veri.
