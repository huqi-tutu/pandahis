---
name: data-cleaning
description: Pandahis data cleaning and validation toolkit for historiography pipeline
trigger: data cleaning, validation, dedupe, CBDB alignment
---

# Pandahis Data Cleaning Toolkit

## Overview

Quality gate between historiography-index (Phase 1) and historiography-compose (Phase 3).

Non-invasive: does not modify existing skills, runs as a separate validation layer.

## Features

1. **Schema Validation** - Phase 1/3 JSON output validated against Zod schemas
2. **Deduplication** - Detect unmerged aliases of the same person
3. **CBDB Alignment** - Cross-reference with China Biographical Database
4. **Quality Report** - Scored data quality metrics

## Tools

| Tool | Purpose |
|------|---------|
| validate-index.mjs | Phase 1 index JSON schema check |
| validate-compose.mjs | Phase 3 compose JSON schema check |
| dedupe-names.mjs | Duplicate person name detection |
| align-reference.mjs | CBDB cross-reference validation |

## Quick Start

`ash
cd scripts/data-cleaning
npm install
node validate-index.mjs --input ../../data/sample.json
`

## Schemas (Zod-based)

- schemas/index-schema.mjs - Phase 1 index JSON
- schemas/compose-schema.mjs - Phase 3 compose JSON
- schemas/reference-schema.mjs - CBDB reference data

## External References

### CBDB (China Biographical Database)

Harvard-maintained structured database with 500K+ historical person records.
GitHub: https://github.com/cbdb-project

### Alternative Tools

| Project | GitHub | Use Case |
|---------|--------|----------|
| OpenRefine | github.com/OpenRefine/OpenRefine | Interactive data cleaning GUI |
| Dedupe | github.com/dedupeio/dedupe | ML-based fuzzy dedup |
| Great Expectations | github.com/great-expectations/great_expectations | Data quality testing |
| HanLP | github.com/hankcs/HanLP | Classical Chinese NLP |

## Workflow Integration

`
Phase 1 JSON -> validate-index -> dedupe-names -> Phase 2/3
Phase 3 JSON -> validate-compose -> align-reference -> Final Data
`