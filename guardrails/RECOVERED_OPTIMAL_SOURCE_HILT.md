---
type: handoff
title: Recovered Optimal Source For HILT
description: Recovery note linking the accepted topology source, refinement source, and validation images.
tags:
  - recovery
  - hilt
  - mbb
  - source-triage
---

# Recovered Optimal Source For HILT

## Recovery Summary

The uploaded HILT target image matches the refined model lineage:

```text
src/mbb_3d_truss_pymoto.py
  -> outputs/runs/3d_20260708_151202/
  -> src/refine_3d_print_mesh.py
  -> outputs/runs/refined_20260708_155144/
```

The recovered topology source was snapshotted here:

```text
src/recovered/mbb_3d_truss_pymoto_recovered_3d_20260708_151202.py
```

The recovered refinement source was snapshotted here:

```text
src/recovered/refine_3d_print_mesh_recovered_refined_20260708_155144.py
```

## Source Run

Accepted topology/design-intent run:

```text
outputs/runs/3d_20260708_151202/
```

Important manifest values:

```text
nx=56
ny=14
nz=8
volume_fraction=0.42
filter_radius=1.8
reference_arch_envelope=True
mirror_symmetry=True
print_mesh_watertight=True
print_mesh_body_count=1
symmetry_mean_abs_error=2.480771963960597e-17
```

## Refined Output Run

Screenshot-like refined output:

```text
outputs/runs/refined_20260708_155144/
```

Important verification values:

```text
print_mesh_watertight=True
print_mesh_body_count=1
bounds_min=0.000000,0.000000,0.000000
bounds_max=210.000000,40.000000,24.000000
```

## HILT Validation Images

Uploaded target copy:

```text
outputs/hilt_validation/user_reference_attachment.png
```

Density-preview validation image:

```text
outputs/hilt_validation/hilt_recovered_source_validation.png
```

STL orthographic validation image:

```text
outputs/hilt_validation/hilt_recovered_stl_orthographic_validation.png
```

Use the orthographic validation image for sharper visual review because it is generated directly from:

```text
outputs/runs/refined_20260708_155144/mesh/optimized_3d_mbb_truss_refined_print.stl
```

## Notes

- The source currently at `src/mbb_3d_truss_pymoto.py` already matches the recovered topology source lineage.
- The HILT image is closer to `refined_20260708_155144` than to the later CAD-style reconstruction.
- Do not replace this recovered source with `src/reconstruct_cad_style_beam.py` when the target is the uploaded HILT screenshot.
