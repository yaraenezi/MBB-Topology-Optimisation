---
type: project
title: MBB Topology Optimisation
description: Curated OpenKB-style package for an initial 2D MBB truss and recovered 3D MBB truss source lineage.
tags:
  - mbb-beam
  - topology-optimisation
  - pymoto
  - stl
---

# MBB Topology Optimisation

This repository contains the accepted source code and STL artifacts for:

- an initial 2D MBB topology optimisation baseline;
- a recovered 3D MBB truss topology source;
- the recovered 3D print-refinement source used for HILT validation.

Failed/intermediate iterations are intentionally excluded from the GitHub package.

## OpenKB Structure

- [`OPENKB.md`](OPENKB.md) - curated knowledge index for this package.
- [`src/`](src/) - accepted Python source code.
- [`outputs/`](outputs/) - accepted STL artifacts and validation outputs.
- [`guardrails/`](guardrails/index.md) - handoffs, triage notes, and development guardrails.

## Included Source

2D baseline:

```text
src/mbb_beam_pymoto.py
```

Recovered 3D topology source:

```text
src/recovered/mbb_3d_truss_pymoto_recovered_3d_20260708_151202.py
```

Recovered 3D refinement source:

```text
src/recovered/refine_3d_print_mesh_recovered_refined_20260708_155144.py
```

## Included STL Files

2D baseline STL:

```text
outputs/runs/20260708_143004/mesh/optimized_mbb_beam.stl
```

Recovered 3D topology STL:

```text
outputs/runs/3d_20260708_151202/mesh/optimized_3d_mbb_truss_print_smooth.stl
```

Recovered 3D refined print STL:

```text
outputs/runs/refined_20260708_155144/mesh/optimized_3d_mbb_truss_refined_print.stl
```

## Verification

See:

```text
outputs/runs/20260708_143004/verification/watertightness.txt
outputs/runs/3d_20260708_151202/verification/watertightness.txt
outputs/runs/refined_20260708_155144/verification/refined_mesh_report.txt
```

## Dependencies

Install:

```powershell
python -m pip install -r requirements.txt
```

## HILT Validation

Recovered-source validation images are in:

```text
outputs/hilt_validation/
```

The sharpest comparison image is:

```text
outputs/hilt_validation/hilt_recovered_stl_orthographic_validation.png
```

## Copyright Boundary

PDF-derived material, converted article markdown, raw screenshots, and other copyrighted reference assets are intentionally excluded from this GitHub package.
