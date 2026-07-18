import {
  repairMermaidChart,
  sanitizeMermaidChart,
} from '../src/utils/mermaidSanitize.ts'

const cases = [
  {
    name: 'bare multi-word source',
    input: 'flowchart TD\n  Parallel processing -->|No recurrence| RNN',
    expected: '  Parallel_processing["Parallel processing"] --> |No recurrence| RNN',
  },
  {
    name: 'orphan closing quote',
    input: 'flowchart TD\n  Parallel processing" -->|No recurrence| RNN',
    expected: '  Parallel_processing["Parallel processing"] --> |No recurrence| RNN',
  },
  {
    name: 'unclosed bracket label',
    input: 'flowchart TD\n  A[Parallel processing" -->|No recurrence| RNN',
    expected: '  A["Parallel processing"] --> |No recurrence| RNN',
  },
  {
    name: 'quantum ket notation in labels',
    input: 'flowchart TD\n  C["|0\u27E9"] -->|AND| D["|1\u27E9"]',
    expected: '  C["#124;0>"] --> |AND| D["#124;1>"]',
  },
  {
    name: 'valid quoted pattern',
    input: 'flowchart TD\n  A["Parallel processing"] -->|No recurrence| B["RNN"]',
    expected: '  A["Parallel processing"] --> |No recurrence| B["RNN"]',
  },
]

let passed = 0
for (const { name, input, expected } of cases) {
  const repaired = repairMermaidChart(input)
  const line = repaired.split('\n')[1] ?? ''
  if (line === expected) {
    console.log(`PASS [${name}]`)
    console.log(`  -> ${line}`)
    passed++
  } else {
    console.log(`FAIL [${name}]`)
    console.log(`  expected: ${expected}`)
    console.log(`  got:      ${line}`)
  }
}

console.log(`\n${passed}/${cases.length} passed`)
process.exit(passed === cases.length ? 0 : 1)
