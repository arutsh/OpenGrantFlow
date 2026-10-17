#!/usr/bin/env node
import { ESLint } from 'eslint'

// Ratchet: fail if lint problems exceed this count. Lower it as problems
// get fixed on touch — never raise it to paper over a new regression.
const BASELINE = 87

const eslint = new ESLint()
const results = await eslint.lintFiles(['.'])
const total = results.reduce((sum, r) => sum + r.errorCount + r.warningCount, 0)

if (total > BASELINE) {
  console.error(
    `Lint problems: ${total} (baseline: ${BASELINE}). This introduces new lint errors/warnings — fix them before merging.`,
  )
  process.exit(1)
}

if (total < BASELINE) {
  console.log(
    `Lint problems: ${total} (baseline: ${BASELINE}). Lower BASELINE in scripts/check-lint-baseline.mjs to ${total} to lock in the improvement.`,
  )
}

console.log(`Lint check passed: ${total} problem(s), baseline ${BASELINE}.`)
