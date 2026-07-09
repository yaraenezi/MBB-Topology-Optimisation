"""Optimize a true 3D MBB beam block with pyMOTO 2.0.1.

This script is the 3D counterpart to ``mbb_beam_pymoto.py``. It starts from a
rectangular 3D block, applies MBB-style supports and a top loading nose, runs
topology optimization, then exports a watertight voxel-surface STL.
"""

from datetime import datetime
from pathlib import Path

import numpy as np
import trimesh
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
from scipy.ndimage import gaussian_filter, zoom
from skimage.measure import marching_cubes
from trimesh.remesh import subdivide_loop
from trimesh.smoothing import filter_taubin


SPAN_MM = 210.0
HEIGHT_MM = 40.0
DEPTH_MM = 24.0

NX = 56
NY = 14
NZ = 8

VOLUME_FRACTION = 0.42
FILTER_RADIUS = 1.8
MIN_DENSITY = 1e-3
LOAD_MAGNITUDE = 1.0
MAX_ITERATIONS = 55
CHANGE_TOLERANCE = 0.015
THRESHOLD = 0.42
EXPORT_UPSCALE = 2
EXPORT_SMOOTH_SIGMA = 0.75
PRINT_SUBDIVISION_ITERATIONS = 1
PRINT_SMOOTHING_ITERATIONS = 12
ENFORCE_REFERENCE_ENVELOPE = True
ENFORCE_MIRROR_SYMMETRY = True
SHELL_THICKNESS_ELEMENTS = 2
BOTTOM_CHORD_ELEMENTS = 2
END_POST_ELEMENTS = 2
CENTER_LOAD_RIB_HALF_WIDTH = 1

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "outputs"
RUNS_DIR = OUT_DIR / "runs"


def apply_mirror_symmetry(field):
    """Mirror material across span and depth for a symmetric MBB reference shape."""
    shaped = field.reshape((NX, NY, NZ), order="F")
    mirrored = 0.25 * (
        shaped
        + shaped[::-1, :, :]
        + shaped[:, :, ::-1]
        + shaped[::-1, :, ::-1]
    )
    return mirrored.reshape(-1, order="F")


def reference_arch_masks():
    """Passive masks for an arched shell-infill beam similar to the PDF reference."""
    passive_solid = np.zeros((NX, NY, NZ), dtype=bool)
    passive_void = np.zeros((NX, NY, NZ), dtype=bool)

    for ix in range(NX):
        x = (ix + 0.5) / NX
        arch = 0.38 + 0.60 * np.sin(np.pi * x) ** 0.55
        top_index = int(np.clip(np.floor(arch * NY), 1, NY - 1))

        passive_void[ix, top_index + 1 :, :] = True
        passive_solid[ix, :BOTTOM_CHORD_ELEMENTS, :] = True
        shell_low = max(0, top_index - SHELL_THICKNESS_ELEMENTS + 1)
        passive_solid[ix, shell_low : top_index + 1, :] = True

    passive_solid[:END_POST_ELEMENTS, :, :] &= ~passive_void[:END_POST_ELEMENTS, :, :]
    passive_solid[-END_POST_ELEMENTS:, :, :] &= ~passive_void[-END_POST_ELEMENTS:, :, :]

    mid = NX // 2
    rib = slice(mid - CENTER_LOAD_RIB_HALF_WIDTH, mid + CENTER_LOAD_RIB_HALF_WIDTH + 1)
    passive_solid[rib, NY // 2 :, :] &= ~passive_void[rib, NY // 2 :, :]

    passive_solid[:, :, :1] |= passive_solid[:, :, -1:]
    passive_solid[:, :, -1:] |= passive_solid[:, :, :1]
    passive_solid &= ~passive_void
    free = ~(passive_solid | passive_void)
    return (
        passive_solid.reshape(-1, order="F"),
        passive_void.reshape(-1, order="F"),
        free.reshape(-1, order="F"),
    )


def apply_passive_masks(x, passive_solid, passive_void):
    x = x.copy()
    x[passive_solid] = 1.0
    x[passive_void] = 0.0
    if ENFORCE_MIRROR_SYMMETRY:
        x = apply_mirror_symmetry(x)
        x[passive_solid] = 1.0
        x[passive_void] = 0.0
    return x


def oc_update(x, dfdx, target_volume, free_mask, passive_solid, passive_void, move=0.18):
    """Optimality criteria update with passive regions and mirror symmetry."""
    lower, upper = 0.0, 100000.0
    safe_grad = np.minimum(dfdx, -1e-12)
    target_free_volume = max(target_volume - np.count_nonzero(passive_solid), 0.0)

    while upper - lower > 1e-4:
        mid = 0.5 * (lower + upper)
        candidate = x.copy()
        free_candidate = x[free_mask] * np.sqrt(-safe_grad[free_mask] / mid)
        free_candidate = np.clip(free_candidate, x[free_mask] - move, x[free_mask] + move)
        candidate[free_mask] = np.clip(free_candidate, 0.0, 1.0)
        candidate = apply_passive_masks(candidate, passive_solid, passive_void)

        if np.sum(candidate[free_mask]) > target_free_volume:
            lower = mid
        else:
            upper = mid

    change = float(np.max(np.abs(candidate - x)))
    return candidate, change


def support_pad_nodes(domain, x_index):
    """Nodes in a small lower bearing pad at one beam end."""
    z_indices = range(0, NZ + 1)
    y_indices = range(0, 2)
    return [domain.nodes[x_index, iy, iz] for iy in y_indices for iz in z_indices]


def load_nose_nodes(domain):
    """Top midspan nodes under the loading nose."""
    x_indices = range(NX // 2 - 1, NX // 2 + 2)
    z_indices = range(NZ // 2 - 1, NZ // 2 + 2)
    return [domain.nodes[ix, NY, iz] for ix in x_indices for iz in z_indices]


def build_load_case(domain):
    """Return boundary dofs and load vector for the 3D MBB block."""
    ndof = 3
    boundary_dofs = []

    for node in support_pad_nodes(domain, 0):
        boundary_dofs.extend([ndof * node, ndof * node + 1, ndof * node + 2])

    for node in support_pad_nodes(domain, NX):
        boundary_dofs.extend([ndof * node + 1, ndof * node + 2])

    force = np.zeros(domain.nnodes * ndof)
    nose_nodes = load_nose_nodes(domain)
    for node in nose_nodes:
        force[ndof * node + 1] = -LOAD_MAGNITUDE / len(nose_nodes)

    return np.asarray(sorted(set(boundary_dofs)), dtype=int), force


def optimize_mbb_3d():
    domain = VoxelDomain(NX, NY, NZ)
    boundary_dofs, force = build_load_case(domain)
    if ENFORCE_REFERENCE_ENVELOPE:
        passive_solid, passive_void, free_mask = reference_arch_masks()
    else:
        passive_solid = np.zeros(domain.nel, dtype=bool)
        passive_void = np.zeros(domain.nel, dtype=bool)
        free_mask = np.ones(domain.nel, dtype=bool)

    initial_density = np.ones(domain.nel) * VOLUME_FRACTION
    initial_density = apply_passive_masks(initial_density, passive_solid, passive_void)
    design = Signal("density_3d", state=initial_density)

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

    target_volume = VOLUME_FRACTION * np.count_nonzero(~passive_void)
    history = []

    for iteration in range(1, MAX_ITERATIONS + 1):
        network.reset()
        compliance.sensitivity = 1.0
        network.sensitivity()
        design.state, change = oc_update(
            design.state,
            design.sensitivity,
            target_volume,
            free_mask,
            passive_solid,
            passive_void,
        )
        network.response()

        mean_density = float(np.sum(design.state) / np.count_nonzero(~passive_void))
        history.append((iteration, float(compliance.state), mean_density, change))
        print(
            f"it={iteration:03d} compliance={float(compliance.state):.6g} "
            f"volume={mean_density:.3f} change={change:.3f}"
        )

        if change < CHANGE_TOLERANCE:
            break

    density = np.asarray(filtered.state).reshape((NX, NY, NZ), order="F")
    return domain, density, history


def add_quad(triangles, v0, v1, v2, v3):
    triangles.append((v0, v1, v2))
    triangles.append((v0, v2, v3))


def make_voxel_surface(mask):
    dx = SPAN_MM / NX
    dy = HEIGHT_MM / NY
    dz = DEPTH_MM / NZ
    triangles = []

    for ix in range(NX):
        for iy in range(NY):
            for iz in range(NZ):
                if not mask[ix, iy, iz]:
                    continue

                x0, x1 = ix * dx, (ix + 1) * dx
                y0, y1 = iy * dy, (iy + 1) * dy
                z0, z1 = iz * dz, (iz + 1) * dz

                if ix == 0 or not mask[ix - 1, iy, iz]:
                    add_quad(triangles, (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0))
                if ix == NX - 1 or not mask[ix + 1, iy, iz]:
                    add_quad(triangles, (x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))
                if iy == 0 or not mask[ix, iy - 1, iz]:
                    add_quad(triangles, (x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1))
                if iy == NY - 1 or not mask[ix, iy + 1, iz]:
                    add_quad(triangles, (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0))
                if iz == 0 or not mask[ix, iy, iz - 1]:
                    add_quad(triangles, (x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0))
                if iz == NZ - 1 or not mask[ix, iy, iz + 1]:
                    add_quad(triangles, (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))

    return triangles


def face_neighbor_count(mask, ix, iy, iz):
    count = 0
    for dx, dy, dz in (
        (-1, 0, 0),
        (1, 0, 0),
        (0, -1, 0),
        (0, 1, 0),
        (0, 0, -1),
        (0, 0, 1),
    ):
        nx, ny, nz = ix + dx, iy + dy, iz + dz
        if 0 <= nx < NX and 0 <= ny < NY and 0 <= nz < NZ and mask[nx, ny, nz]:
            count += 1
    return count


def choose_removal(mask, density, first, second):
    first_score = (face_neighbor_count(mask, *first), density[first])
    second_score = (face_neighbor_count(mask, *second), density[second])
    return first if first_score < second_score else second


def remove_edge_only_contacts(mask, density):
    """Remove diagonal voxel contacts that create non-manifold STL edges."""
    cleaned = mask.copy()
    changed = True

    while changed:
        changed = False
        to_remove = set()

        for ix in range(NX):
            for iy in range(NY):
                for iz in range(NZ):
                    if not cleaned[ix, iy, iz]:
                        continue

                    checks = (
                        ((1, 1, 0), ((1, 0, 0), (0, 1, 0))),
                        ((1, -1, 0), ((1, 0, 0), (0, -1, 0))),
                        ((1, 0, 1), ((1, 0, 0), (0, 0, 1))),
                        ((1, 0, -1), ((1, 0, 0), (0, 0, -1))),
                        ((0, 1, 1), ((0, 1, 0), (0, 0, 1))),
                        ((0, 1, -1), ((0, 1, 0), (0, 0, -1))),
                    )

                    for diagonal, fillers in checks:
                        dx, dy, dz = diagonal
                        other = (ix + dx, iy + dy, iz + dz)
                        if not (
                            0 <= other[0] < NX
                            and 0 <= other[1] < NY
                            and 0 <= other[2] < NZ
                            and cleaned[other]
                        ):
                            continue

                        filler_a = (
                            ix + fillers[0][0],
                            iy + fillers[0][1],
                            iz + fillers[0][2],
                        )
                        filler_b = (
                            ix + fillers[1][0],
                            iy + fillers[1][1],
                            iz + fillers[1][2],
                        )
                        has_filler_a = (
                            0 <= filler_a[0] < NX
                            and 0 <= filler_a[1] < NY
                            and 0 <= filler_a[2] < NZ
                            and cleaned[filler_a]
                        )
                        has_filler_b = (
                            0 <= filler_b[0] < NX
                            and 0 <= filler_b[1] < NY
                            and 0 <= filler_b[2] < NZ
                            and cleaned[filler_b]
                        )

                        if not has_filler_a and not has_filler_b:
                            to_remove.add(
                                choose_removal(cleaned, density, (ix, iy, iz), other)
                            )

        if to_remove:
            for voxel in to_remove:
                cleaned[voxel] = False
            changed = True

    return cleaned


def write_ascii_stl(triangles, path):
    def normal(triangle):
        a, b, c = (np.asarray(vertex, dtype=float) for vertex in triangle)
        vector = np.cross(b - a, c - a)
        length = np.linalg.norm(vector)
        return vector / length if length > 0 else vector

    with path.open("w", encoding="ascii") as file:
        file.write("solid optimized_3d_mbb_truss\n")
        for triangle in triangles:
            nx, ny, nz = normal(triangle)
            file.write(f"  facet normal {nx:.9g} {ny:.9g} {nz:.9g}\n")
            file.write("    outer loop\n")
            for vx, vy, vz in triangle:
                file.write(f"      vertex {vx:.9g} {vy:.9g} {vz:.9g}\n")
            file.write("    endloop\n")
            file.write("  endfacet\n")
        file.write("endsolid optimized_3d_mbb_truss\n")


def voxel_triangles_to_mesh(triangles):
    vertices = []
    vertex_index = {}
    faces = []

    for triangle in triangles:
        face = []
        for vertex in triangle:
            key = tuple(float(value) for value in vertex)
            if key not in vertex_index:
                vertex_index[key] = len(vertices)
                vertices.append(key)
            face.append(vertex_index[key])
        faces.append(face)

    return trimesh.Trimesh(
        vertices=np.asarray(vertices, dtype=float),
        faces=np.asarray(faces, dtype=np.int64),
        process=True,
    )


def make_smooth_print_mesh(density):
    """Create a smoother triangular mesh from the density volume."""
    scalar = gaussian_filter(density.astype(float), sigma=EXPORT_SMOOTH_SIGMA)
    high_res = zoom(scalar, EXPORT_UPSCALE, order=3)
    spacing = (
        SPAN_MM / NX / EXPORT_UPSCALE,
        HEIGHT_MM / NY / EXPORT_UPSCALE,
        DEPTH_MM / NZ / EXPORT_UPSCALE,
    )

    padded = np.pad(high_res, 1, mode="constant", constant_values=0.0)
    vertices, faces, _, _ = marching_cubes(
        padded,
        level=THRESHOLD,
        spacing=spacing,
        allow_degenerate=False,
    )
    vertices -= np.asarray(spacing)

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()

    if PRINT_SUBDIVISION_ITERATIONS > 0:
        vertices, faces = subdivide_loop(
            mesh.vertices,
            mesh.faces,
            iterations=PRINT_SUBDIVISION_ITERATIONS,
        )
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)

    filter_taubin(mesh, lamb=0.5, nu=0.53, iterations=PRINT_SMOOTHING_ITERATIONS)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    return mesh


def watertightness_report(triangles):
    edge_count = {}
    for triangle in triangles:
        for start, end in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((triangle[start], triangle[end])))
            edge_count[edge] = edge_count.get(edge, 0) + 1

    open_edges = [edge for edge, count in edge_count.items() if count != 2]
    return {
        "watertight": len(open_edges) == 0,
        "triangles": len(triangles),
        "unique_edges": len(edge_count),
        "non_manifold_or_open_edges": len(open_edges),
    }


def mesh_report(mesh):
    return {
        "watertight": bool(mesh.is_watertight),
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "body_count": int(len(mesh.split(only_watertight=False))),
        "volume": float(mesh.volume) if mesh.is_watertight else float("nan"),
        "area": float(mesh.area),
    }


def write_projection_pgm(volume, axis, path):
    projection = np.max(volume, axis=axis)
    if axis == 2:
        image = np.flipud(projection.T)
    elif axis == 1:
        image = np.flipud(projection.T)
    else:
        image = np.flipud(projection.T)

    image = (np.clip(image, 0.0, 1.0) * 255).astype(np.uint8)
    with path.open("wb") as file:
        file.write(f"P5\n{image.shape[1]} {image.shape[0]}\n255\n".encode("ascii"))
        file.write(image.tobytes())


def make_run_dirs():
    run_id = "3d_" + datetime.now().strftime("%Y%m%d_%H%M%S")
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


def write_manifest(path, run_id, voxel_report, print_report, raw_voxels, solid_voxels):
    lines = [
        "3D MBB truss optimization run",
        f"run_id={run_id}",
        f"timestamp={run_id.removeprefix('3d_')}",
        f"span_mm={SPAN_MM}",
        f"height_mm={HEIGHT_MM}",
        f"depth_mm={DEPTH_MM}",
        f"nx={NX}",
        f"ny={NY}",
        f"nz={NZ}",
        f"volume_fraction={VOLUME_FRACTION}",
        f"filter_radius={FILTER_RADIUS}",
        f"threshold={THRESHOLD}",
        f"export_upscale={EXPORT_UPSCALE}",
        f"export_smooth_sigma={EXPORT_SMOOTH_SIGMA}",
        f"print_subdivision_iterations={PRINT_SUBDIVISION_ITERATIONS}",
        f"print_smoothing_iterations={PRINT_SMOOTHING_ITERATIONS}",
        f"reference_arch_envelope={ENFORCE_REFERENCE_ENVELOPE}",
        f"mirror_symmetry={ENFORCE_MIRROR_SYMMETRY}",
        f"shell_thickness_elements={SHELL_THICKNESS_ELEMENTS}",
        f"raw_solid_voxels={raw_voxels}",
        f"cleaned_solid_voxels={solid_voxels}",
        f"voxel_debug_watertight={voxel_report['watertight']}",
        f"voxel_non_manifold_or_open_edges={voxel_report['non_manifold_or_open_edges']}",
        f"print_mesh_watertight={print_report['watertight']}",
        f"print_mesh_vertices={print_report['vertices']}",
        f"print_mesh_faces={print_report['faces']}",
        f"print_mesh_body_count={print_report['body_count']}",
        f"print_mesh_area={print_report['area']}",
        f"print_mesh_volume={print_report['volume']}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def main():
    OUT_DIR.mkdir(exist_ok=True)
    run_id, run_dir, parts = make_run_dirs()
    domain, density, history = optimize_mbb_3d()

    density_path = parts["density"] / "density_volume.npy"
    density_flat_path = parts["density"] / "density_voxels.csv"
    history_path = parts["history"] / "history.csv"
    voxel_stl_path = parts["mesh"] / "optimized_3d_mbb_truss_voxel_debug.stl"
    print_stl_path = parts["mesh"] / "optimized_3d_mbb_truss_print_smooth.stl"
    report_path = parts["verification"] / "watertightness.txt"
    manifest_path = run_dir / "manifest.txt"

    np.save(density_path, density)
    np.savetxt(
        density_flat_path,
        density.reshape((NX * NY, NZ), order="F"),
        delimiter=",",
        fmt="%.6f",
    )
    np.savetxt(
        history_path,
        np.asarray(history),
        delimiter=",",
        header="iteration,compliance,volume_fraction,max_density_change",
        comments="",
        fmt=["%d", "%.10g", "%.6f", "%.6f"],
    )

    write_projection_pgm(density, axis=2, path=parts["preview"] / "front_projection.pgm")
    write_projection_pgm(density, axis=1, path=parts["preview"] / "top_projection.pgm")
    write_projection_pgm(density, axis=0, path=parts["preview"] / "side_projection.pgm")

    raw_mask = density >= THRESHOLD
    solid_mask = remove_edge_only_contacts(raw_mask, density)
    triangles = make_voxel_surface(solid_mask)
    write_ascii_stl(triangles, voxel_stl_path)
    voxel_report = watertightness_report(triangles)

    print_mesh = make_smooth_print_mesh(density)
    print_mesh.export(print_stl_path)
    print_report = mesh_report(print_mesh)

    report_lines = [
        "3D MBB truss watertightness test",
        f"domain_elements={domain.nel}",
        f"threshold={THRESHOLD}",
        f"raw_solid_voxels={int(np.count_nonzero(raw_mask))}",
        f"solid_voxels={int(np.count_nonzero(solid_mask))}",
        f"voxel_debug_triangles={voxel_report['triangles']}",
        f"voxel_debug_unique_edges={voxel_report['unique_edges']}",
        f"voxel_debug_non_manifold_or_open_edges={voxel_report['non_manifold_or_open_edges']}",
        f"voxel_debug_watertight={voxel_report['watertight']}",
        f"print_mesh_vertices={print_report['vertices']}",
        f"print_mesh_faces={print_report['faces']}",
        f"print_mesh_body_count={print_report['body_count']}",
        f"print_mesh_area={print_report['area']}",
        f"print_mesh_volume={print_report['volume']}",
        f"print_mesh_watertight={print_report['watertight']}",
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="ascii")
    write_manifest(
        manifest_path,
        run_id,
        voxel_report,
        print_report,
        int(np.count_nonzero(raw_mask)),
        int(np.count_nonzero(solid_mask)),
    )
    (OUT_DIR / "latest_3d_run.txt").write_text(str(run_dir) + "\n", encoding="ascii")
    (OUT_DIR / "latest_run.txt").write_text(str(run_dir) + "\n", encoding="ascii")

    print(f"\nOutputs ({run_id})")
    print(f"  run: {run_dir}")
    print(f"  density: {density_path}")
    print(f"  history: {history_path}")
    print(f"  print stl: {print_stl_path}")
    print(f"  voxel debug stl: {voxel_stl_path}")
    print(f"  watertight: {print_report['watertight']} ({report_path})")


if __name__ == "__main__":
    main()
