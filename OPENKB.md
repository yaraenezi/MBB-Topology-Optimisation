---
type: openkb-index
title: MBB Topology Optimisation OpenKB
description: Curated knowledge bundle for the accepted 2D MBB topology baseline and recovered 3D truss source lineage.
tags:
  - mbb
  - topology-optimisation
  - pymoto
  - stl
---

# MBB Topology Optimisation OpenKB

This repository is a curated OpenKB-style package containing only the accepted source code and accepted STL artifacts.

Copyright-sensitive source references, PDF conversions, and raw images are intentionally excluded.

## Included Source

- `src/mbb_beam_pymoto.py` - accepted initial 2D MBB topology optimisation baseline.
- `src/recovered/mbb_3d_truss_pymoto_recovered_3d_20260708_151202.py` - recovered 3D topology source that generated the accepted 3D density/design run.
- `src/recovered/refine_3d_print_mesh_recovered_refined_20260708_155144.py` - recovered refinement source used to produce the HILT-matching print STL.

## Included STL Artifacts

- `outputs/runs/20260708_143004/mesh/optimized_mbb_beam.stl`
- `outputs/runs/3d_20260708_151202/mesh/optimized_3d_mbb_truss_print_smooth.stl`
- `outputs/runs/refined_20260708_155144/mesh/optimized_3d_mbb_truss_refined_print.stl`

## Excluded

Failed and deprecated runs are intentionally excluded from Git:

- `3d_20260708_143408`
- `3d_20260708_143618`
- `3d_20260708_144320`
- `cad_reconstructed_20260708_160036`
- `cad_reconstructed_20260708_160246`

The CAD-style reconstruction is not included because this push targets the initial 2D truss and recovered 3D truss lineage requested for HILT validation.

## Triage Notes

See:

- `guardrails/LOCAL_GIT_HANDOFF.md`
- `guardrails/RECOVERED_OPTIMAL_SOURCE_HILT.md`
- `guardrails/HANDOFF.md`
