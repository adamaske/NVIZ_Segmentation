use std::collections::VecDeque;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use ndarray::Array4;
use neuroformats::{FsMgh, FsMghData, write_mgh};

// =============================================================================
// Goal
// =============================================================================
//
// Orchestrate the full head-segmentation pipeline from Rust.
// Once stable, this logic moves into NIRWizard.
//
// Pipeline:
//   1. verify_setup   — Docker, GPU, FastSurfer image, FreeSurfer license
//   2. run_fastsurfer — FastSurfer inside Docker (grey + white matter)
//   3. voxelize       — Native Rust: reads aseg/T1/brainmask MGZ files,
//                       builds a 1mm³ labeled volume, writes head_labels.mgz
//                       Labels: 0=background, 1=skull, 2=CSF, 3=GM, 4=WM
//   4. meshify        — Python: marching-cubes OBJ per tissue for 3D viewing
//
// =============================================================================

// ------------------------------------------------------------------
// Tissue label values
// ------------------------------------------------------------------

#[allow(dead_code)] // background is 0 by default (Array4::zeros), never explicitly written
const LABEL_BG: u8    = 0;
const LABEL_SKULL: u8 = 1;
const LABEL_CSF: u8   = 2;
const LABEL_GM: u8    = 3;
const LABEL_WM: u8    = 4;

// FreeSurfer aseg label sets (from FreeSurfer LUT)
const WM_LABELS: &[i32]  = &[2, 41, 7, 46, 77, 78, 79, 192, 251, 252, 253, 254, 255];
const GM_LABELS: &[i32]  = &[3, 42, 8, 47, 10, 11, 12, 13, 17, 18, 26, 28,
                               16, 49, 50, 51, 52, 53, 54, 58, 60];
const CSF_LABELS: &[i32] = &[4, 5, 14, 15, 24, 31, 43, 44, 63, 72];

// ------------------------------------------------------------------
// Config
// ------------------------------------------------------------------

struct Config {
    /// Absolute path to the input T1 NIfTI file.
    mri_path: PathBuf,
    /// Absolute path to the output root folder.
    output_folder: PathBuf,
    /// Subject ID — used as the sub-folder name inside output_folder.
    subject_id: String,
    /// Folder that contains license.txt (FreeSurfer license).
    license_folder: PathBuf,
    /// Folder containing the Python helper scripts.
    scripts_folder: PathBuf,
}

impl Config {
    fn subject_dir(&self) -> PathBuf {
        self.output_folder.join(&self.subject_id)
    }
}

// ------------------------------------------------------------------
// Generic helpers
// ------------------------------------------------------------------

/// Convert a Windows path to forward-slash form for Docker volume mounts.
fn docker_path(p: &Path) -> String {
    p.to_string_lossy().replace('\\', "/")
}

/// Run a subprocess with inherited stdio.  Streams output live to the terminal.
fn run(label: &str, cmd: &mut Command) -> Result<(), String> {
    println!("  [RUN] {label}");
    let status = cmd
        .status()
        .map_err(|e| format!("[{label}] failed to launch process: {e}"))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!(
            "[{label}] exited with code {:?}",
            status.code().unwrap_or(-1)
        ))
    }
}

// ------------------------------------------------------------------
// MGH data extraction helpers
// ------------------------------------------------------------------

/// Extract voxel data from any MGH dtype as f32 (used for T1 intensities).
fn mgh_as_f32(mgh: &FsMgh) -> Result<Array4<f32>, String> {
    if let Some(a) = &mgh.data.mri_float { return Ok(a.clone()); }
    if let Some(a) = &mgh.data.mri_uchar { return Ok(a.mapv(|v| v as f32)); }
    if let Some(a) = &mgh.data.mri_int   { return Ok(a.mapv(|v| v as f32)); }
    if let Some(a) = &mgh.data.mri_short { return Ok(a.mapv(|v| v as f32)); }
    Err("MGH volume contains no data".to_string())
}

/// Extract voxel data from any MGH dtype as i32 (used for integer labels).
fn mgh_as_i32(mgh: &FsMgh) -> Result<Array4<i32>, String> {
    if let Some(a) = &mgh.data.mri_int   { return Ok(a.clone()); }
    if let Some(a) = &mgh.data.mri_short { return Ok(a.mapv(|v| v as i32)); }
    if let Some(a) = &mgh.data.mri_uchar { return Ok(a.mapv(|v| v as i32)); }
    if let Some(a) = &mgh.data.mri_float { return Ok(a.mapv(|v| v as i32)); }
    Err("MGH volume contains no data".to_string())
}

// ------------------------------------------------------------------
// Head-mask computation
// ------------------------------------------------------------------

/// Flood-fill background from all 6-face border voxels where T1 <= threshold.
/// Returns a flat Vec<bool> (row-major x,y,z) where true = inside head.
///
/// This is equivalent to scikit-image `binary_fill_holes` after thresholding:
/// any interior dark voxel (CSF pocket, air sinus) enclosed by bright tissue
/// will be marked as "inside head" because it is not reachable from the border.
fn compute_head_mask(t1: &Array4<f32>, threshold: f32) -> Vec<bool> {
    let (nx, ny, nz, _) = t1.dim();
    let n = nx * ny * nz;
    let mut is_bg = vec![false; n];
    let mut queue: VecDeque<(usize, usize, usize)> = VecDeque::new();

    let idx = |x: usize, y: usize, z: usize| x * ny * nz + y * nz + z;

    // Seed: all boundary voxels below the intensity threshold.
    for x in 0..nx {
        for y in 0..ny {
            for z in 0..nz {
                let on_border = x == 0 || x == nx - 1
                    || y == 0 || y == ny - 1
                    || z == 0 || z == nz - 1;
                if on_border && t1[[x, y, z, 0]] <= threshold {
                    let i = idx(x, y, z);
                    if !is_bg[i] {
                        is_bg[i] = true;
                        queue.push_back((x, y, z));
                    }
                }
            }
        }
    }

    // 6-connected BFS through voxels below the threshold.
    const DIRS: [(i32, i32, i32); 6] = [
        (-1, 0, 0), (1, 0, 0),
        (0, -1, 0), (0, 1, 0),
        (0, 0, -1), (0, 0, 1),
    ];
    while let Some((x, y, z)) = queue.pop_front() {
        for (dx, dy, dz) in DIRS {
            let (x2, y2, z2) = (x as i32 + dx, y as i32 + dy, z as i32 + dz);
            if x2 < 0 || x2 >= nx as i32
                || y2 < 0 || y2 >= ny as i32
                || z2 < 0 || z2 >= nz as i32
            {
                continue;
            }
            let (x2, y2, z2) = (x2 as usize, y2 as usize, z2 as usize);
            let i = idx(x2, y2, z2);
            if !is_bg[i] && t1[[x2, y2, z2, 0]] <= threshold {
                is_bg[i] = true;
                queue.push_back((x2, y2, z2));
            }
        }
    }

    // head_mask = NOT background
    is_bg.into_iter().map(|b| !b).collect()
}

// ------------------------------------------------------------------
// Step 1 — verify_setup
// ------------------------------------------------------------------

fn verify_setup(cfg: &Config) -> Result<(), String> {
    println!("\n=== Step 1: Verify Setup ===");

    // Docker daemon running?  (`docker info` connects to the daemon;
    // `docker --version` only reads the local binary and always succeeds.)
    run(
        "docker info (daemon check)",
        Command::new("docker").arg("info"),
    )
    .map_err(|e| format!("{e}\n  → Is Docker Desktop running? Start it and retry."))?;

    // GPU accessible inside Docker?
    run(
        "nvidia-smi in Docker",
        Command::new("docker").args([
            "run", "--gpus", "all", "--rm",
            "nvidia/cuda:12.0.0-base-ubuntu22.04", "nvidia-smi",
        ]),
    )
    .map_err(|e| format!("{e}\n  → Enable GPU support in Docker Desktop."))?;

    // FastSurfer image present locally?
    run(
        "inspect deepmi/fastsurfer:latest",
        Command::new("docker").args(["image", "inspect", "deepmi/fastsurfer:latest"]),
    )?;

    // FreeSurfer license file present?
    let license = cfg.license_folder.join("license.txt");
    if !license.is_file() {
        return Err(format!(
            "FreeSurfer license not found at: {}",
            license.display()
        ));
    }
    println!("  [OK] license.txt found");

    // Input MRI file present?
    if !cfg.mri_path.is_file() {
        return Err(format!("Input MRI not found: {}", cfg.mri_path.display()));
    }
    println!("  [OK] Input MRI found");

    println!("  All checks passed.");
    Ok(())
}

// ------------------------------------------------------------------
// Step 2 — run_fastsurfer
// ------------------------------------------------------------------

fn run_fastsurfer(cfg: &Config) -> Result<(), String> {
    println!("\n=== Step 2: Run FastSurfer ===");

    // Idempotent — skip if aseg.mgz already exists.
    if cfg.subject_dir().join("mri").join("aseg.mgz").is_file() {
        println!("  aseg.mgz already exists — skipping FastSurfer.");
        return Ok(());
    }

    let input_folder = cfg.mri_path.parent().ok_or("mri_path has no parent")?;
    let filename = cfg
        .mri_path
        .file_name()
        .ok_or("mri_path has no filename")?
        .to_string_lossy()
        .to_string();

    fs::create_dir_all(&cfg.output_folder)
        .map_err(|e| format!("Cannot create output folder: {e}"))?;

    run(
        "docker run deepmi/fastsurfer",
        Command::new("docker").args([
            "run", "--gpus", "all",
            "-v", &format!("{}:/data",       docker_path(input_folder)),
            "-v", &format!("{}:/output",     docker_path(&cfg.output_folder)),
            "-v", &format!("{}:/fs_license", docker_path(&cfg.license_folder)),
            "--rm", "--user", "root",
            "deepmi/fastsurfer:latest",
            "--fs_license", "/fs_license/license.txt",
            "--t1", &format!("/data/{filename}"),
            "--sid", &cfg.subject_id,
            "--sd", "/output",
            "--3T", "--threads", "max", "--allow_root",
        ]),
    )?;

    println!("  FastSurfer complete.");
    Ok(())
}

// ------------------------------------------------------------------
// Step 3 — build labeled voxel volume (native Rust via neuroformats)
// ------------------------------------------------------------------
//
// Reads aseg.mgz, T1.mgz, brainmask.mgz directly — no Python or Docker needed.
// Writes head_labels.mgz with the same grid geometry as the input volumes.
//

fn run_voxelization(cfg: &Config) -> Result<(), String> {
    println!("\n=== Step 3: Build Labeled Voxel Volume (native Rust) ===");

    let out_path = cfg.subject_dir().join("mri").join("head_labels.mgz");
    if out_path.is_file() {
        println!("  head_labels.mgz already exists — skipping.");
        return Ok(());
    }

    let aseg_path = cfg.subject_dir().join("mri").join("aseg.mgz");
    let t1_path   = cfg.subject_dir().join("mri").join("T1.mgz");
    let bm_path   = cfg.subject_dir().join("mri").join("brainmask.mgz");

    println!("  Loading aseg.mgz ...");
    let aseg_mgh = FsMgh::from_file(&aseg_path)
        .map_err(|e| format!("Cannot read aseg.mgz: {e}"))?;

    println!("  Loading T1.mgz ...");
    let t1_mgh = FsMgh::from_file(&t1_path)
        .map_err(|e| format!("Cannot read T1.mgz: {e}"))?;

    println!("  Loading brainmask.mgz ...");
    let bm_mgh = FsMgh::from_file(&bm_path)
        .map_err(|e| format!("Cannot read brainmask.mgz: {e}"))?;

    let aseg_data = mgh_as_i32(&aseg_mgh)?;
    let t1_data   = mgh_as_f32(&t1_mgh)?;
    let bm_data   = mgh_as_i32(&bm_mgh)?;

    let (nx, ny, nz, _) = aseg_data.dim();
    println!("  Volume: {nx} × {ny} × {nz}");

    // Head mask: flood-fill background from border, head = everything else.
    println!("  Computing head mask (threshold = 15) ...");
    let head_mask = compute_head_mask(&t1_data, 15.0);

    // Build output label volume.
    println!("  Mapping tissue labels ...");
    let mut labels = Array4::<u8>::zeros((nx, ny, nz, 1));

    let flat_idx = |x: usize, y: usize, z: usize| x * ny * nz + y * nz + z;

    // 1. Skull/scalp: inside head mask but outside brain.
    for x in 0..nx {
        for y in 0..ny {
            for z in 0..nz {
                if head_mask[flat_idx(x, y, z)] && bm_data[[x, y, z, 0]] == 0 {
                    labels[[x, y, z, 0]] = LABEL_SKULL;
                }
            }
        }
    }

    // 2-4. CSF → GM → WM from aseg (each pass has higher priority).
    for ((x, y, z, _), &lbl) in aseg_data.indexed_iter() {
        if CSF_LABELS.contains(&lbl) { labels[[x, y, z, 0]] = LABEL_CSF; }
        if GM_LABELS.contains(&lbl)  { labels[[x, y, z, 0]] = LABEL_GM; }
        if WM_LABELS.contains(&lbl)  { labels[[x, y, z, 0]] = LABEL_WM; }
    }

    // Print voxel counts.
    let mut counts = [0usize; 5];
    for &v in labels.iter() {
        counts[v as usize] += 1;
    }
    let total = labels.len() as f64;
    for (i, name) in ["background", "skull", "CSF", "grey matter", "white matter"]
        .iter()
        .enumerate()
    {
        println!(
            "  {:15}: {:>10} voxels  ({:.1}%)",
            name, counts[i], 100.0 * counts[i] as f64 / total
        );
    }

    // Write output MGZ.  Reuse aseg header for geometry (same voxel grid),
    // but set dtype = 0 (MRI_UCHAR) to match our u8 data.
    let mut out_header = aseg_mgh.header;
    out_header.dtype    = 0; // MRI_UCHAR
    out_header.dim4len  = 1;

    let out_mgh = FsMgh {
        header: out_header,
        data: FsMghData {
            mri_uchar: Some(labels),
            mri_float: None,
            mri_int:   None,
            mri_short: None,
        },
    };

    println!("  Writing: {}", out_path.display());
    write_mgh(&out_path, &out_mgh)
        .map_err(|e| format!("Cannot write head_labels.mgz: {e}"))?;

    println!("  [OK] head_labels.mgz written.");
    Ok(())
}

// ------------------------------------------------------------------
// Step 4 — meshify for visualization
// ------------------------------------------------------------------
//
// Calls scripts/meshify_labels.py which runs marching cubes per tissue
// label and exports one OBJ per tissue type so they can be inspected
// in any 3D viewer (Blender, MeshLab, 3D Slicer, etc.).
// nibabel can read .mgz natively so no format conversion is needed.
//

fn run_meshify(cfg: &Config) -> Result<(), String> {
    println!("\n=== Step 4: Meshify Labels for Visualization ===");

    let labels_vol = cfg.subject_dir().join("mri").join("head_labels.mgz");
    let surf_dir   = cfg.subject_dir().join("surf");
    fs::create_dir_all(&surf_dir)
        .map_err(|e| format!("Cannot create surf dir: {e}"))?;

    let script = cfg.scripts_folder.join("meshify_labels.py");
    run(
        "python meshify_labels.py",
        Command::new("python")
            .arg(&script)
            .arg(&labels_vol)
            .arg(&surf_dir),
    )?;

    println!("  Meshes written to: {}", surf_dir.display());
    Ok(())
}

// ------------------------------------------------------------------
// Step 5 — nonlinear CVS registration to MNI template
// ------------------------------------------------------------------
//
// Runs mri_cvs_register inside the same FastSurfer Docker image.
// FreeSurfer is bundled inside deepmi/fastsurfer, so no extra image needed.
//
// Output (written by mri_cvs_register into the subject dir):
//   mri/cvs/final_CVSmorph_tocvs_avg35_inMNI152.m3z   ← the warp field
//   mri/cvs/final_CVSmorph_tocvs_avg35_inMNI152.mgz   ← warped brain
//

fn run_cvs_registration(cfg: &Config) -> Result<(), String> {
    println!("\n=== Step 5: CVS Nonlinear Registration to MNI ===");

    let warp_path = cfg
        .subject_dir()
        .join("mri")
        .join("cvs")
        .join("final_CVSmorph_tocvs_avg35_inMNI152.m3z");

    if warp_path.is_file() {
        println!("  CVS warp already exists — skipping.");
        return Ok(());
    }

    run(
        "mri_cvs_register",
        Command::new("docker").args([
            "run", "--gpus", "all",
            "-v", &format!("{}:/output",     docker_path(&cfg.output_folder)),
            "-v", &format!("{}:/fs_license", docker_path(&cfg.license_folder)),
            "--rm", "--user", "root",
            "deepmi/fastsurfer:latest",
            // mri_cvs_register is a FreeSurfer command bundled in the image
            "mri_cvs_register",
            "--mov",      &cfg.subject_id,
            "--mni152reg",                  // target = cvs_avg35_inMNI152
            "--sd",       "/output",
            "--nocleanup",                  // keep intermediate files for debugging
        ]),
    )?;

    println!("  CVS warp written to: {}", warp_path.display());
    Ok(())
}

// ------------------------------------------------------------------
// Step 6 — apply CVS warp to sensitivity matrix
// ------------------------------------------------------------------
//
// mri_vol2vol with --m3z applies the dense nonlinear warp.
// Input:  sensitivity_matrix.mgz  (in subject native space)
// Output: sensitivity_mni.mgz     (in cvs_avg35_inMNI152 space)
//

fn apply_cvs_warp(cfg: &Config, sensitivity_path: &Path) -> Result<(), String> {
    println!("\n=== Step 6: Apply CVS Warp to Sensitivity Matrix ===");

    let out_path = cfg.subject_dir().join("mri").join("sensitivity_mni.mgz");

    if out_path.is_file() {
        println!("  sensitivity_mni.mgz already exists — skipping.");
        return Ok(());
    }

    // The m3z warp file lives inside the subject dir which is already mounted
    let warp_file = format!(
        "/output/{}/mri/cvs/final_CVSmorph_tocvs_avg35_inMNI152.m3z",
        cfg.subject_id
    );

    run(
        "mri_vol2vol (apply CVS warp)",
        Command::new("docker").args([
            "run", "--gpus", "all",
            "-v", &format!("{}:/output",     docker_path(&cfg.output_folder)),
            "-v", &format!("{}:/fs_license", docker_path(&cfg.license_folder)),
            "--rm", "--user", "root",
            "deepmi/fastsurfer:latest",
            "mri_vol2vol",
            "--mov",  &format!("/output/{}/mri/sensitivity_matrix.mgz", cfg.subject_id),
            "--s",    &cfg.subject_id,
            "--sd",   "/output",
            "--m3z",  &warp_file,
            "--noDefM3zPath",               // warp path given explicitly above
            "--o",    &format!("/output/{}/mri/sensitivity_mni.mgz", cfg.subject_id),
            "--trilin",                     // trilinear interp (use --nearest for label vols)
        ]),
    )?;

    println!("  Warped sensitivity: {}", out_path.display());
    Ok(())
}
// ------------------------------------------------------------------
// Main
// ------------------------------------------------------------------

fn main() {
    // Hard-coded paths for local testing.
    // In NIRWizard these will be supplied at runtime.
    let project_root = PathBuf::from("C:/dev/NVIZ_Segmentation");

    let cfg = Config {
        mri_path:       project_root.join("input").join("sub-116_ses-BL_T1w.nii.gz"),
        output_folder:  project_root.join("output"),
        subject_id:     "sub-116".to_string(),
        license_folder: project_root.join("license"),
        scripts_folder: project_root.join("scripts"),
    };

    println!("==============================================");
    println!(" NVIZ Segmentation Pipeline");
    println!("==============================================");
    println!("  MRI     : {}", cfg.mri_path.display());
    println!("  Subject : {}", cfg.subject_id);
    println!("  Output  : {}", cfg.output_folder.display());
    println!("==============================================");

    let steps: &[(&str, fn(&Config) -> Result<(), String>)] = &[
        ("verify_setup",   verify_setup),
        ("run_fastsurfer", run_fastsurfer),
        ("voxelization",   run_voxelization),
        ("meshify",        run_meshify),
    ];

    for (name, step) in steps {
        if let Err(e) = step(&cfg) {
            eprintln!("\n[FAIL] Step '{name}': {e}");
            std::process::exit(1);
        }
    }

    println!();
    println!("==============================================");
    println!(" Pipeline complete!");
    println!("==============================================");
    println!(
        "  Labels volume : output/{}/mri/head_labels.mgz",
        cfg.subject_id
    );
    println!(
        "  Meshes        : output/{}/surf/{{skull,csf,grey_matter,white_matter}}.obj",
        cfg.subject_id
    );
    println!();
    println!("  Open the OBJ files in Blender / MeshLab / 3D Slicer to verify.");
}
