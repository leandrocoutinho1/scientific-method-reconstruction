# Pipeline Overview

## Step 1 — Collect scientific papers

Select a small set of scientific articles related to machine learning applications.

## Step 2 — Parse PDFs with GROBID

Use GROBID to convert PDFs into structured TEI/XML and JSON representations.

## Step 3 — Extract methodology sections

Identify sections such as:

- Methods
- Methodology
- Materials and Methods
- Experimental Setup
- Experiments

## Step 4 — Create artificial gaps

Artificially remove excerpts from methodology sections to simulate missing content.

## Step 5 — Reconstruct missing excerpts

Use language models to reconstruct the removed text based on surrounding context.

## Step 6 — Evaluate results

Compare reconstructed text with the original excerpt using qualitative and quantitative metrics.
