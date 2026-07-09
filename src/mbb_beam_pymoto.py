"""Optimize a rectangular MBB beam with pyMOTO 2.0.1.

The model follows the loading sketch supplied with the task:
- rectangular span length: 210 mm
- left support: pinned at the lower-left node
- right support: roller at the lower-right node
- loading nose: downward point load at the top midspan

The final density field is thresholded, extruded into a thin triangle mesh, and
checked for watertightness by verifying that every mesh edge is used exactly
twice.
"""

from datetime import datetime
from pathlib import Path

import numpy as np
from pymoto import (
    AssembleStiffness,
    DensityFilter,
    EinSum,
    LinSolve,
    MathExpression,
    Network,
    Signal,
    VoxelDomain,
)


SPAN_MM = 210.0
HEIGHT_MM = 40.0
NX = 126
NY = 24

VOLUME_FRACTION = 0.42
FILTER_RADIUS = 2.0
MIN_DENSITY = 1e-3
LOAD_MAGNITUDE = 1.0
MAX_ITERATIONS = 90
CHANGE_TOLERANCE = 0.01
THRESHOLD = 0.50
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "outputs"
RUNS_DIR = OUT_DIR / "runs"


def oc_update(x, dfdx, target_volume, move=0.2):
    """Optimality criteria update with a fixed total material volume."""
    lower, upper = 0.0, 100000.0
    safe_grad = np.minimum(dfdx, -1e-12)

    while upper - lower > 1e-4:
        mid = 0.5 * (lower + upper)
        candidate = x * np.sqrt(-safe_grad / mid)
        candidate = np.clip(candidate, x - move, x + move)
        candidate = np.clip(candidate, 0.0, 1.0)

        if np.sum(candidate) > target_volume:
            lower = mid
        else:
            upper = mid

    change = float(np.max(np.abs(candidate - x)))
    return candidate, change


def build_load_case(domain):
    """Return boundary dofs and load vector for the photographed MBB setup."""
    ndof = 2
    left_support = domain.nodes[0, 0]
    right_support = domain.nodes[NX, 0]
    load_node = domain.nodes[NX // 2, NY]

    boundary_dofs = np.array(
        [
            ndof * left_support,
            ndof * left_support + 1,
            ndof * right_support + 1,
        ],
        dtype=int,
    )

    force = np.zeros(domain.nnodes * ndof)
    force[ndof * load_node + 1] = -LOAD_MAGNITUDE
    return boundary_dofs, force


def optimize_mbb():
    domain = VoxelDomain(NX, NY)
    boundary_dofs, force = build_load_case(domain)
    design = Signal("density", state=np.ones(domain.nel) * VOLUME_FRACTION)

    with Network() as network:
        filtered = DensityFilter(domain=domain, radius=FILTER_RADIUS)(design)
        stiffness_density = MathExpression(
            expression=f"{MIN_DENSITY} + {1.0 - MIN_DENSITY}*inp0^3"
        )(filtered)
        stiffness = AssembleStiffness(domain=domain, bc=boundary_dofs)(
            stiffness_density
        )
        displacement = LinSolve(symmetric=True, positive_definite=True)(
            stiffness, force
        )
        compliance = EinSum(expression="i,i->")(displacement, force)

    target_volume = VOLUME_FRACTION * domain.nel
    history = []
    change = 1.0

    for iteration in range(1, MAX_ITERATIONS + 1):
        network.reset()
        compliance.sensitivity = 1.0
        network.sensitivity()
        design.state, change = oc_update(design.state, design.sensitivity, target_volume)
        network.response()

        mean_density = float(np.mean(design.state))
        history.append((iteration, float(compliance.state), mean_density, change))
        print(
            f"it={iteration:03d} compliance={float(compliance.state):.6g} "
            f"volume={mean_density:.3f} change={change:.3f}"
        )

        if change < CHANGE_TOLERANCE:
            break

    return domain, np.asarray(filtered.state).reshape((NX, NY), order="F"), history


def write_pgm(density, path):
    """Write a dependency-free grayscale preview of the optimized density."""
    image = np.flipud((np.clip(density.T, 0.0, 1.0) * 255).astype(np.uint8))
    with path.open("wb") as file:
        file.write(f"P5\n{image.shape[1]} {image.shape[0]}\n255\n".encode("ascii"))
        file.write(image.tobytes())


def add_quad(triangles, v0, v1, v2, v3):
    triangles.append((v0, v1, v2))
    triangles.append((v0, v2, v3))


def make_extruded_mesh(mask, thickness_mm):
    dx = SPAN_MM / NX
    dy = HEIGHT_MM / NY
    z0, z1 = 0.0, thickness_mm
    triangles = []

    for ix in range(NX):
        for iy in range(NY):
            if not mask[ix, iy]:
                continue

            x0, x1 = ix * dx, (ix + 1) * dx
            y0, y1 = iy * dy, (iy + 1) * dy

            front = ((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0))
            back = ((x0, y0, z1), (x0, y1, z1), (x1, y1, z1), (x1, y0, z1))
            add_quad(triangles, *front)
            add_quad(triangles, *back)

            if ix == 0 or not mask[ix - 1, iy]:
                add_quad(
                    triangles,
                    (x0, y0, z0),
                    (x0, y1, z0),
                    (x0, y1, z1),
                    (x0, y0, z1),
                )
            if ix == NX - 1 or not mask[ix + 1, iy]:
                add_quad(
                    triangles,
                    (x1, y0, z0),
                    (x1, y0, z1),
                    (x1, y1, z1),
                    (x1, y1, z0),
                )
            if iy == 0 or not mask[ix, iy - 1]:
                add_quad(
                    triangles,
                    (x0, y0, z0),
                    (x0, y0, z1),
                    (x1, y0, z1),
                    (x1, y0, z0),
                )
            if iy == NY - 1 or not mask[ix, iy + 1]:
                add_quad(
                    triangles,
                    (x0, y1, z0),
                    (x1, y1, z0),
                    (x1, y1, z1),
                    (x0, y1, z1),
                )

    return triangles


def write_ascii_stl(triangles, path):
    def normal(triangle):
        a, b, c = (np.asarray(vertex, dtype=float) for vertex in triangle)
        vector = np.cross(b - a, c - a)
        length = np.linalg.norm(vector)
        return vector / length if length > 0 else vector

    with path.open("w", encoding="ascii") as file:
        file.write("solid optimized_mbb_beam\n")
        for triangle in triangles:
            nx, ny, nz = normal(triangle)
            file.write(f"  facet normal {nx:.9g} {ny:.9g} {nz:.9g}\n")
            file.write("    outer loop\n")
            for vx, vy, vz in triangle:
                file.write(f"      vertex {vx:.9g} {vy:.9g} {vz:.9g}\n")
            file.write("    endloop\n")
            file.write("  endfacet\n")
        file.write("endsolid optimized_mbb_beam\n")


def watertightness_report(triangles):
    edge_count = {}
    for triangle in triangles:
        for start, end in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((triangle[start], triangle[end])))
            edge_count[edge] = edge_count.get(edge, 0) + 1

    boundary_edges = [edge for edge, count in edge_count.items() if count != 2]
    return {
        "watertight": len(boundary_edges) == 0,
        "triangles": len(triangles),
        "unique_edges": len(edge_count),
        "non_manifold_or_open_edges": len(boundary_edges),
    }


def make_run_dirs(timestamp=None):
    """Create a timestamped, part-wise output directory for one run."""
    run_id = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / run_id
    parts = {
        "density": run_dir / "density",
        "history": run_dir / "history",
        "preview": run_dir / "preview",
        "mesh": run_dir / "mesh",
        "verification": run_dir / "verification",
    }

    for directory in parts.values():
        directory.mkdir(parents=True, exist_ok=False)

    return run_id, run_dir, parts


def write_manifest(path, run_id, report):
    manifest_lines = [
        "MBB beam optimization run",
        f"run_id={run_id}",
        f"timestamp={run_id}",
        f"span_mm={SPAN_MM}",
        f"height_mm={HEIGHT_MM}",
        f"nx={NX}",
        f"ny={NY}",
        f"volume_fraction={VOLUME_FRACTION}",
        f"filter_radius={FILTER_RADIUS}",
        f"threshold={THRESHOLD}",
        f"watertight={report['watertight']}",
        f"non_manifold_or_open_edges={report['non_manifold_or_open_edges']}",
    ]
    path.write_text("\n".join(manifest_lines) + "\n", encoding="ascii")


def main():
    OUT_DIR.mkdir(exist_ok=True)
    run_id, run_dir, parts = make_run_dirs()
    domain, density, history = optimize_mbb()

    density_path = parts["density"] / "density.csv"
    history_path = parts["history"] / "history.csv"
    preview_path = parts["preview"] / "density_preview.pgm"
    stl_path = parts["mesh"] / "optimized_mbb_beam.stl"
    report_path = parts["verification"] / "watertightness.txt"
    manifest_path = run_dir / "manifest.txt"

    np.savetxt(density_path, density.T, delimiter=",", fmt="%.6f")
    np.savetxt(
        history_path,
        np.asarray(history),
        delimiter=",",
        header="iteration,compliance,volume_fraction,max_density_change",
        comments="",
        fmt=["%d", "%.10g", "%.6f", "%.6f"],
    )
    write_pgm(density, preview_path)

    solid_mask = density >= THRESHOLD
    triangles = make_extruded_mesh(solid_mask, thickness_mm=HEIGHT_MM / NY)
    write_ascii_stl(triangles, stl_path)
    report = watertightness_report(triangles)

    report_lines = [
        "MBB beam watertightness test",
        f"domain_elements={domain.nel}",
        f"threshold={THRESHOLD}",
        f"solid_elements={int(np.count_nonzero(solid_mask))}",
        f"triangles={report['triangles']}",
        f"unique_edges={report['unique_edges']}",
        f"non_manifold_or_open_edges={report['non_manifold_or_open_edges']}",
        f"watertight={report['watertight']}",
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="ascii")
    write_manifest(manifest_path, run_id, report)
    (OUT_DIR / "latest_run.txt").write_text(str(run_dir) + "\n", encoding="ascii")

    print(f"\nOutputs ({run_id})")
    print(f"  run: {run_dir}")
    print(f"  density: {density_path}")
    print(f"  history: {history_path}")
    print(f"  preview: {preview_path}")
    print(f"  stl: {stl_path}")
    print(f"  watertight: {report['watertight']} ({report_path})")


if __name__ == "__main__":
    main()
