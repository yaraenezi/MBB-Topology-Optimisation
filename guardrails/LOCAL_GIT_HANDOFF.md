---
type: handoff
title: Local Git Handoff - MBB Beam Source Iterations
description: Source-code evolution, output mapping, and triage notes for selecting the optimal MBB beam solution.
tags:
  - handoff
  - local-git
  - source-history
  - triage
---

# Local Git Handoff - Source Iterations

## Status

The `mbb` folder is not currently initialized as a local Git repository. This file is a local handoff for future Git work, not evidence of commits.

Do not initialize Git, create commits, add remotes, push, or connect to GitHub unless the user explicitly asks.

Project folder:

```text
C:\Users\SASCA\Desktop\YARA ALENEZI -SURE\mbb
```

## Source Files To Track

Current source files:

```text
src/mbb_beam_pymoto.py
src/mbb_3d_truss_pymoto.py
src/refine_3d_print_mesh.py
src/reconstruct_cad_style_beam.py
```

Current documentation/control files:

```text
README.md
SPEC.md
requirements.txt
requirements-docs.txt
guardrails/HANDOFF.md
guardrails/LOCAL_GIT_HANDOFF.md
wiki/3d-truss.md
references/markdown/shell-infill-derived-equations.md
references/markdown/mesh-smoothing.md
```

## Iteration Timeline

### 1. Initial 2D MBB Topology Optimization

Source:

```text
src/mbb_beam_pymoto.py
```

Purpose:

- Build a 2D rectangular MBB beam in pyMOTO.
- Apply left pin, right roller, and top-midspan load.
- Export a thin extruded STL from the optimized 2D density.
- Perform an edge-count watertightness test.

Representative outputs:

```text
outputs/runs/20260708_142600_legacy/
outputs/runs/20260708_143004/
```

Result:

- Useful baseline.
- Watertight.
- Too flat and voxel-like for the final visual target.

Triage:

- Keep as a baseline and reproducibility reference.
- Do not use as final print/design source.

### 2. First True 3D Block Topology Optimization

Source:

```text
src/mbb_3d_truss_pymoto.py
```

Purpose:

- Move from 2D extrusion to a true 3D block topology optimization.
- Use pyMOTO `VoxelDomain(nx, ny, nz)`.
- Export a voxel-surface STL.

Representative outputs:

```text
outputs/runs/3d_20260708_143408/
outputs/runs/3d_20260708_143618/
```

Result:

- Confirmed true 3D behavior across depth.
- Early `3d_20260708_143408` had non-manifold/open edges.
- `3d_20260708_143618` added cleanup and became watertight.
- Still looked jagged and blocky.

Triage:

- Keep for validating true 3D pyMOTO setup.
- Not visually acceptable as final model.

### 3. Higher-Resolution Smooth 3D Print Mesh

Source:

```text
src/mbb_3d_truss_pymoto.py
```

Major source changes:

- Increased 3D analysis resolution.
- Added `scikit-image` marching cubes.
- Added `trimesh` smoothing/export.
- Added Loop subdivision and Taubin smoothing.
- Added smooth print STL beside voxel debug STL.

Representative output:

```text
outputs/runs/3d_20260708_144320/
```

Result:

- Print mesh was watertight.
- Smoother than voxel STL.
- Still looked like a raw smoothed topology mesh, not a reconstructed engineering figure.

Triage:

- Keep as the best pure topology-driven printable mesh.
- Do not use as final aesthetic source.

### 4. Reference-Matched Symmetric Shell-Infill Topology

Source:

```text
src/mbb_3d_truss_pymoto.py
```

Major source changes:

- Added mirror symmetry across span/depth.
- Added arched passive shell envelope.
- Added passive bottom chord, load rib, and support regions.
- Increased volume fraction to support a shell-infill-like structure.
- Increased filter radius to reduce local stress-like material concentration.

Representative output:

```text
outputs/runs/3d_20260708_151202/
```

Result:

```text
print_mesh_watertight=True
print_mesh_body_count=1
symmetry_mean_abs_error=2.48e-17
```

Result quality:

- Much closer to the CMAME2017 shell-infill reference.
- Preserved five openings and symmetry.
- Still retained topology-mesh waviness and non-CAD-like boundaries.

Triage:

- Keep as the accepted topology/design-intent density source.
- Use this run as the guide for manual/CAD-style reconstruction.

### 5. Post-Processing Cleanup Of Accepted Topology

Source:

```text
src/refine_3d_print_mesh.py
```

Purpose:

- Start from the accepted 3D density result.
- Do not rerun optimization.
- Smooth density field.
- Export a higher-resolution marching-cubes STL.
- Force a flat FDM bottom.
- Preserve nominal bounds.

Representative output:

```text
outputs/runs/refined_20260708_155144/
```

Result:

```text
watertight=True
body_count=1
bounds=210 x 40 x 24 mm
faces=410880
```

Result quality:

- Much smoother and printable.
- Still visibly a smoothed topology optimization mesh.
- Did not satisfy the later requirement for CAD-quality spline reconstruction.

Triage:

- Keep as the best mesh-processing/post-processing solution.
- Useful comparison against CAD reconstruction.
- Not the final preferred source if the goal is engineering-journal appearance.

### 6. CAD-Style Spline Reconstruction

Source:

```text
src/reconstruct_cad_style_beam.py
```

Major source design:

- Does not smooth or remesh existing STL.
- Reconstructs the 2D profile from intentional Bezier/spline curves.
- Creates one continuous arched outer profile.
- Keeps bottom perfectly straight.
- Defines five smooth openings.
- Makes central opening taller and narrower.
- Makes adjacent openings taller and more slender.
- Mirrors left and right openings.
- Extrudes the clean profile into a watertight solid using `shapely`, `mapbox-earcut`, and `trimesh`.

Failed/obsolete intermediate output:

```text
outputs/runs/cad_reconstructed_20260708_160036/
```

Reason:

- Early raster/marching-cubes CAD attempt was visually useful but not manifold.
- Do not use as final output.

Current preferred output:

```text
outputs/runs/cad_reconstructed_20260708_160246/
```

Preferred STL:

```text
outputs/runs/cad_reconstructed_20260708_160246/mesh/mbb_beam_cad_reconstructed_print.stl
```

Verification:

```text
watertight=True
body_count=1
bounds=210 x 38 x 24 mm
vertices=2466
faces=4948
```

Triage:

- Current best solution source.
- Continue refinement by editing spline control points in `src/reconstruct_cad_style_beam.py`.
- Do not refine this by smoothing the STL. Adjust the profile curves instead.

## Optimal Source Recommendation

Use this source as the current optimal solution path:

```text
src/reconstruct_cad_style_beam.py
```

Use this output as the current best printable artifact:

```text
outputs/runs/cad_reconstructed_20260708_160246/mesh/mbb_beam_cad_reconstructed_print.stl
```

Use this topology run as the design-intent guide:

```text
outputs/runs/3d_20260708_151202/
```

## What To Keep

Keep all source scripts for traceability:

- `mbb_beam_pymoto.py` - baseline 2D topology.
- `mbb_3d_truss_pymoto.py` - topology/design-intent generator.
- `refine_3d_print_mesh.py` - mesh-cleanup experiment.
- `reconstruct_cad_style_beam.py` - current preferred CAD-style source.

Keep all timestamped outputs until the user asks for cleanup. They document the decision path.

## What Not To Use As Final

Avoid using these as final print/design artifacts:

```text
outputs/runs/3d_20260708_143408/
outputs/runs/3d_20260708_143618/
outputs/runs/3d_20260708_144320/
outputs/runs/cad_reconstructed_20260708_160036/
```

They are useful for audit/history only.

## Local Git Commit Plan If Requested Later

If the user later asks to initialize or commit locally, use a staged commit sequence like:

1. `docs: add project guardrails and reference handoffs`
2. `feat: add baseline pyMOTO MBB topology workflows`
3. `feat: add 3D topology optimization and smooth print export`
4. `feat: add PDF-derived shell-infill references`
5. `feat: add CAD-style spline beam reconstruction`

Do not run these Git actions unless explicitly prompted.

## Future Triage Checklist

When comparing solution sources, evaluate:

- Does it preserve the five main openings?
- Is the bottom edge flat for FDM?
- Is the mesh watertight and one body?
- Does it preserve nominal size?
- Does it look intentionally reconstructed rather than noisy?
- Are changes made in source curves/parameters rather than manual STL edits?

For the current design target, the CAD-style reconstruction wins this triage.
