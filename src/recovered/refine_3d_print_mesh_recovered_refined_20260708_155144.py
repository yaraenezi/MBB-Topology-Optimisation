"""Refine an existing 3D MBB density result into a smoother print STL.

This is a geometry cleanup pass, not a new topology optimization. It preserves
the existing density/cutout pattern while using a higher-resolution isosurface,
stronger smoothing, and a pinned flat bottom for FDM printing.
"""

from datetime import datetime
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageOps
from scipy.ndimage import gaussian_filter, zoom
from skimage.measure import marching_cubes
from trimesh.remesh import subdivide_loop
from trimesh.smoothing import filter_taubin


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "outputs"
RUNS_DIR = OUT_DIR / "runs"

SPAN_MM = 210.0
HEIGHT_MM = 40.0
DEPTH_MM = 24.0

THRESHOLD = 0.42
UPSCALE = 4
GAUSSIAN_SIGMA = 1.15
LOOP_SUBDIVISION_ITERATIONS = 1
TAUBIN_ITERATIONS = 32
BOTTOM_FLAT_BAND_MM = 2.2
MIN_WALL_PRESERVE_SIGMA = 0.55


def latest_3d_run():
    latest_path = OUT_DIR / "latest_3d_run.txt"
    if latest_path.exists():
        return Path(latest_path.read_text(encoding="ascii").strip())

    runs = sorted(RUNS_DIR.glob("3d_*"))
    if not runs:
        raise FileNotFoundError("No 3D runs found under outputs/runs.")
    return runs[-1]


def make_refined_run_dirs(source_run):
    run_id = "refined_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / run_id
    parts = {
        "density": run_dir / "density",
        "mesh": run_dir / "mesh",
        "preview": run_dir / "preview",
        "verification": run_dir / "verification",
    }

    for directory in parts.values():
        directory.mkdir(parents=True, exist_ok=False)

    (run_dir / "source_run.txt").write_text(str(source_run) + "\n", encoding="ascii")
    return run_id, run_dir, parts


def clean_density_field(density):
    """Smooth density while retaining wall thickness around main cutouts."""
    broad = gaussian_filter(density.astype(float), sigma=GAUSSIAN_SIGMA)
    preserve = gaussian_filter(density.astype(float), sigma=MIN_WALL_PRESERVE_SIGMA)
    blended = 0.72 * broad + 0.28 * preserve

    # Keep the FDM bottom chord strong and flat through the scalar field.
    bottom_layers = max(1, int(round(density.shape[1] * BOTTOM_FLAT_BAND_MM / HEIGHT_MM)))
    blended[:, :bottom_layers, :] = np.maximum(blended[:, :bottom_layers, :], 0.95)
    return np.clip(blended, 0.0, 1.0)


def marching_cubes_mesh(density):
    nx, ny, nz = density.shape
    high_res = zoom(density, UPSCALE, order=3)
    spacing = (
        SPAN_MM / nx / UPSCALE,
        HEIGHT_MM / ny / UPSCALE,
        DEPTH_MM / nz / UPSCALE,
    )

    padded = np.pad(high_res, 1, mode="constant", constant_values=0.0)
    vertices, faces, _, _ = marching_cubes(
        padded,
        level=THRESHOLD,
        spacing=spacing,
        allow_degenerate=False,
    )
    vertices -= np.asarray(spacing)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=True)


def fit_to_nominal_bounds(mesh):
    vertices = mesh.vertices.copy()

    for axis, target in ((0, SPAN_MM), (2, DEPTH_MM)):
        min_value = vertices[:, axis].min()
        max_value = vertices[:, axis].max()
        vertices[:, axis] = (vertices[:, axis] - min_value) * target / (max_value - min_value)

    min_y = vertices[:, 1].min()
    vertices[:, 1] -= min_y
    max_y = vertices[:, 1].max()
    if max_y > HEIGHT_MM:
        vertices[:, 1] *= HEIGHT_MM / max_y

    mesh.vertices = vertices


def flatten_bottom(mesh):
    vertices = mesh.vertices.copy()
    bottom_band = vertices[:, 1] <= BOTTOM_FLAT_BAND_MM
    vertices[bottom_band, 1] = 0.0
    mesh.vertices = vertices
    mesh.fix_normals()


def refine_mesh(density):
    smoothed_density = clean_density_field(density)
    mesh = marching_cubes_mesh(smoothed_density)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()

    if LOOP_SUBDIVISION_ITERATIONS:
        vertices, faces = subdivide_loop(
            mesh.vertices,
            mesh.faces,
            iterations=LOOP_SUBDIVISION_ITERATIONS,
        )
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)

    filter_taubin(mesh, lamb=0.45, nu=0.54, iterations=TAUBIN_ITERATIONS)
    fit_to_nominal_bounds(mesh)
    flatten_bottom(mesh)
    mesh.remove_unreferenced_vertices()
    mesh.merge_vertices()
    mesh.fix_normals()
    return mesh, smoothed_density


def mesh_report(mesh):
    return {
        "watertight": bool(mesh.is_watertight),
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "body_count": int(len(mesh.split(only_watertight=False))),
        "area": float(mesh.area),
        "volume": float(mesh.volume) if mesh.is_watertight else float("nan"),
        "bounds_min": mesh.bounds[0],
        "bounds_max": mesh.bounds[1],
    }


def write_preview(density, path):
    front = np.max(density, axis=2).T
    front = np.flipud(front)
    image = Image.fromarray((np.clip(front, 0.0, 1.0) * 255).astype("uint8"), mode="L")
    image = image.resize((1120, 280), Image.Resampling.BICUBIC)
    image = ImageOps.colorize(image, black=(245, 245, 245), white=(0, 155, 70))
    image.save(path)


def write_report(path, run_id, source_run, report):
    lines = [
        "Refined 3D MBB print mesh report",
        f"run_id={run_id}",
        f"source_run={source_run}",
        f"threshold={THRESHOLD}",
        f"upscale={UPSCALE}",
        f"gaussian_sigma={GAUSSIAN_SIGMA}",
        f"wall_preserve_sigma={MIN_WALL_PRESERVE_SIGMA}",
        f"loop_subdivision_iterations={LOOP_SUBDIVISION_ITERATIONS}",
        f"taubin_iterations={TAUBIN_ITERATIONS}",
        f"bottom_flat_band_mm={BOTTOM_FLAT_BAND_MM}",
        f"print_mesh_watertight={report['watertight']}",
        f"print_mesh_vertices={report['vertices']}",
        f"print_mesh_faces={report['faces']}",
        f"print_mesh_body_count={report['body_count']}",
        f"print_mesh_area={report['area']}",
        f"print_mesh_volume={report['volume']}",
        "bounds_min=" + ",".join(f"{value:.6f}" for value in report["bounds_min"]),
        "bounds_max=" + ",".join(f"{value:.6f}" for value in report["bounds_max"]),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def main():
    source_run = latest_3d_run()
    density_path = source_run / "density" / "density_volume.npy"
    if not density_path.exists():
        raise FileNotFoundError(f"Missing density volume: {density_path}")

    run_id, run_dir, parts = make_refined_run_dirs(source_run)
    density = np.load(density_path)
    mesh, smoothed_density = refine_mesh(density)
    report = mesh_report(mesh)

    refined_density_path = parts["density"] / "refined_density_volume.npy"
    stl_path = parts["mesh"] / "optimized_3d_mbb_truss_refined_print.stl"
    preview_path = parts["preview"] / "front_refined_density_preview.png"
    report_path = parts["verification"] / "refined_mesh_report.txt"

    np.save(refined_density_path, smoothed_density)
    mesh.export(stl_path)
    write_preview(smoothed_density, preview_path)
    write_report(report_path, run_id, source_run, report)
    (OUT_DIR / "latest_refined_run.txt").write_text(str(run_dir) + "\n", encoding="ascii")
    (OUT_DIR / "latest_run.txt").write_text(str(run_dir) + "\n", encoding="ascii")

    print(f"Refined run: {run_dir}")
    print(f"STL: {stl_path}")
    print(f"Preview: {preview_path}")
    print(f"Watertight: {report['watertight']}")
    print(f"Faces: {report['faces']}")
    print(f"Bounds: {report['bounds_min']} -> {report['bounds_max']}")


if __name__ == "__main__":
    main()
