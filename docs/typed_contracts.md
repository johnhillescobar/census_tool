# What “Typed Contracts” Means in Layman Terms

In this document, **“typed contracts”** basically means:

> **Very clearly defined data formats that every part of the system must follow.**

In layman terms, think of it like a **standard form** that each step in the software has to fill out correctly before handing it to the next step.

---

## Simple Analogy

Imagine a hospital form:

- Name must be text
- Age must be a number
- Blood type must be one of: `A`, `B`, `AB`, `O`
- Date of birth must be a real date

If someone writes `"blue"` for age, the form gets rejected.

That’s what a **typed contract** is in software:  
a strict agreement about:

- **what fields exist**
- **what type of value each field must be**
- **what values are allowed**
- **what is required vs optional**

---

## In This Document’s Context

They want to add contracts in `src/domain/` using **Pydantic models** with:

- **strict validation**
- **explicit enums**

That means they want objects like `TemporalIntent`, `BenchmarkIntent`, and `ComparisonPlan` to be defined with strict rules.

For example:

### Instead of loose data like this:

```python
{
  "time": "last few years maybe",
  "benchmark": "something like market",
  "normalize": "yes"
}
```

### They want structured, validated data like this:

```python
TemporalIntent(
    start_year=2021,
    end_year=2024,
    missing_year_policy=MissingYearPolicy.FILL_ZERO
)
```

and

```python
BenchmarkIntent(
    target="SP500",
    operator=BenchmarkOperator.VS,
    normalization_mode=NormalizationMode.PERCENT_CHANGE
)
```

---

## What “Typed” Means

“Typed” means the system knows exactly what kind of data each field should hold.

Examples:

- `year` must be an **integer**
- `name` must be a **string**
- `normalization_mode` must be one of a fixed list of allowed values
- `missing_year_policy` cannot be just any random word

So instead of allowing anything, the system enforces rules.

---

## What “Contract” Means

“Contract” means:

> “If one part of the system sends data to another part, it must follow this exact structure.”

It’s like an agreement between components.

For example:

- Planner service promises to output a valid `ComparisonPlan`
- Workflow nodes promise to only pass valid typed objects
- Downstream code can trust the data is already checked

---

## Why This Matters Here

This track is about a **typed harness** — strict data shapes at trust boundaries — **not** a replacement for agent reasoning, retrieval, or API composition.

That means the software gets predictable **validation and math**:

- same **grounded ID choices** → same validated plan and API URLs (harness repeatability)
- agent natural-language wording may vary turn to turn
- no invented FIPS or table codes past the validator
- no loose, malformed data crossing node boundaries

**Do not confuse with legacy "deterministic planning layer":** regex search-text analysis, score-rank table auto-select, and pre-agent `geography_node` halts are **planner-first migration debt**, not harness. See [`agent-first-grounded-planning.md`](agent-first-grounded-planning.md).

Typed contracts help because they remove ambiguity at **boundaries**:

If a user asks something messy like:

> “Compare revenue over the last 3 years against the industry average, and handle missing years by carrying forward values”

the system will turn that into a **strict internal object** with exact fields and allowed values.

That makes planning:

- safer at trust boundaries
- repeatable for **validated plans** (not necessarily identical agent prose)
- easier to test
- easier to debug

**Agent-owned (not typed-contract scope):** semantic Chroma queries, category/table/geo selection, Census `get`/`for`/`in` composition, multi-call tool loops. Domain reference: [`../app_description/CENSUS_DISCUSSION.md`](../app_description/CENSUS_DISCUSSION.md).

---

## What “Strict Validation” Means

It means the system checks the data immediately and rejects bad input.

Examples:

- `"202A"` is not a valid year
- `"compare_kind": "sort of vs"` is not allowed
- `"missing_year_policy": "whatever"` is not allowed unless it matches an approved option

So bad or unclear values fail early instead of causing weird behavior later.

---

## What “Explicit Enums” Means

An **enum** is just a predefined list of allowed choices.

Example:

Instead of allowing any string for benchmark operator, you define:

- `VS`
- `GREATER_THAN`
- `LESS_THAN`

So the user/system can’t send `"kinda compared to"`.

This prevents inconsistent wording and helps guarantee deterministic behavior.

---

## In One Sentence

**Typed contracts are strict, predefined data structures that every part of the system must use so requests and plans are consistent, validated, and predictable.**

---

## Why They Want It in This Plan

Because they’re building a system where:

1. User request gets converted into structured intent (temporal/benchmark harness)
2. **Agent** retrieves evidence, composes API parameters, and executes Census tools
3. Harness validates grounded IDs; comparison **math** stays deterministic

Typed contracts make steps 1 and 3 possible without replacing step 2.

Without them, each step might interpret the data differently.

With them, each step gets a clean, validated object like:

- `TemporalIntent`
- `BenchmarkIntent`
- `ComparisonPlan`

---

## Super Short Version

If you want the simplest explanation:

> **Typed contracts are strict templates for data.**  
> They ensure every part of the app speaks the same language and only passes around well-formed, validated information.

---

## Optional Plain-English Summary of the Three Artifacts

### `TemporalIntent`
This is the system’s clean, structured understanding of **what time period the user means**.

Example:

- last 3 years
- 2021 to 2024
- trailing 12 months

The system normalizes vague time requests into something exact.

### `BenchmarkIntent`
This is the system’s clean, structured understanding of **what the user wants to compare against**.

Example:

- compare to S&P 500
- compare to industry average
- compare to prior year

### `ComparisonPlan`
This is the structured plan for **what comparisons to run and what derived metrics to calculate** (deterministic math). It does **not** replace agent retrieval, table selection, or Census API composition.

---

## Tiny End-to-End Example

### User Request

> “Compare revenue for the last 3 years vs industry average, and fill missing years with zero.”

### Structured Interpretation

```python
TemporalIntent(
    start_year=2022,
    end_year=2024,
    missing_year_policy=MissingYearPolicy.FILL_ZERO
)
```

```python
BenchmarkIntent(
    target="industry_average",
    operator=BenchmarkOperator.VS,
    normalization_mode=NormalizationMode.RAW
)
```

### Final Planning Output

```python
ComparisonPlan(
    query_years=[2022, 2023, 2024],
    primary_metric="revenue",
    benchmark_target="industry_average",
    derived_metrics=["absolute_difference", "percent_difference"],
    missing_year_policy=MissingYearPolicy.FILL_ZERO
)
```

This final plan is:

- structured
- validated
- deterministic
- safe for downstream code to execute