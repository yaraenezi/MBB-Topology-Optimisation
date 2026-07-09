---
type: handoff
title: MBB Beam Project Handoff
description: Current operating notes, project state, outputs, and guardrails for continuing the MBB beam work.
tags:
  - handoff
  - guardrails
  - python
  - topology-optimization
  - cad-reconstruction
---

# MBB Beam Project Handoff

## Project Location

Work from this folder:

```text
C:\Users\SASCA\Desktop\YARA ALENEZI -SURE\mbb
```

Keep MBB-related work inside this folder unless the user explicitly asks otherwise.

## Current Best Result

The preferred model is now the CAD-style spline reconstruction, not the raw topology mesh and not the smoothed marching-cubes refinement.

Use this STL for the current print/design target:

```text
outputs/runs/cad_reconstructed_20260708_160246/mesh/mbb_beam_cad_reconstructed_print.stl
```

Preview:

```text
outputs/runs/cad_reconstructed_20260708_160246/preview/cad_profile_preview.png
```

Verification:

```text
watertight=True
body_count=1
bounds=210 x 38 x 24 mm
vertices=2466
faces=4948
```

This model was reconstructed from intentional spline curves to better match the reference shell-infill beam image. It preserves five main openings, a smooth arched top profile, a straight FDM-friendly bottom, mirrored left/right layout, and clean rounded openings.

## Main Scripts

- `src/mbb_beam_pymoto.py` - original 2D MBB topology optimization workflow.
- `src/mbb_3d_truss_pymoto.py` - true 3D pyMOTO topology optimization workflow.
- `src/refine_3d_print_mesh.py` - post-processes the latest 3D density result into a smoother print mesh.
- `src/reconstruct_cad_style_beam.py` - preferred CAD-style spline reconstruction workflow.

For the current target, continue from:

```powershell
python src\reconstruct_cad_style_beam.py
```

## Output Structure

Generated work is stored under:

```text
outputs/runs/
```

Important runs:

- `3d_20260708_151202/` - accepted reference-matched topology density.
- `refined_20260708_155144/` - smoothed mesh refinement of that topology.
- `cad_reconstructed_20260708_160246/` - current preferred CAD-style printable model.

Pointers:

- `outputs/latest_cad_reconstruction.txt` - latest CAD-style reconstruction.
- `outputs/latest_refined_run.txt` - latest smoothed mesh refinement.
- `outputs/latest_3d_run.txt` - latest 3D topology run.
- `outputs/latest_run.txt` - latest generated run of any type.

## References

Key references are stored locally:

- `references/raw/CMAME2017.pdf` - source paper supplied by the user.
- `references/markdown/CMAME2017.md` - markdown conversion of the PDF with rendered page images.
- `references/markdown/shell-infill-derived-equations.md` - derived shell-infill equations and implementation rules.
- `references/raw/reference_shell_infill_beam_20260708_145947.png` - corrected target reference image.
- `references/raw/previous_refined_model_20260708_155551.png` - previous model comparison screenshot.

## Design Intent

The current aesthetic target is a manually reconstructed shell-infill beam similar to an engineering journal figure, not a raw topology optimization result.

Preserve:

- Overall span and depth.
- Five main openings.
- Smooth arched top shell.
- Straight bottom edge for FDM printing.
- Symmetric left/right structure.
- Taller central opening and slender adjacent openings.
- Smooth ribs and generous rounded hole corners.

Avoid:

- Jagged topology boundaries.
- Wavy outer edges.
- Blob-like holes.
- Thin spikes.
- Narrow necks.
- Sharp internal corners.
- Changing the beam into a completely new design.

## Dependencies

Install project dependencies with:

```powershell
python -m pip install -r requirements.txt
```

Current major dependencies:

- `numpy`
- `pymoto==2.0.1`
- `scikit-image`
- `trimesh`
- `shapely`
- `mapbox-earcut`

Optional PDF conversion dependencies are listed in:

```text
requirements-docs.txt
```

## Verification

For CAD-style reconstruction:

```powershell
python src\reconstruct_cad_style_beam.py
```

Then check the generated report:

```text
outputs/runs/<cad_reconstructed_timestamp>/verification/cad_reconstruction_report.txt
```

Required checks:

```text
watertight=True
body_count=1
bounds_min=0,0,0
```

The current best run has:

```text
bounds_max=210,38,24
```

## Guardrails

- Do not edit system folders, global Python installation files, registry settings, PATH settings, or operating system configuration.
- Do not initialize Git, create commits, push branches, open pull requests, or connect to GitHub unless explicitly prompted.
- Do not move or delete unrelated files from the original intro project.
- Read files before editing and preserve unrelated user changes.
- Keep generated outputs inside timestamped `outputs/runs/` folders.
- Prefer adding small, traceable scripts over overwriting previous successful outputs.

## Recommended Next Step

If continuing refinement, adjust `src/reconstruct_cad_style_beam.py` curve control points rather than smoothing the STL. The profile is now CAD-style and should be refined by moving spline control points for the outer shell and the five openings.
