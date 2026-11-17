use anyhow::{Context, Result};
use colored::*;
use memmap2::MmapMut;
use std::fs::{self, OpenOptions};
use std::path::{Path, PathBuf};

pub const SIG_INELIGIBLE: &[u8] = b"ineligible";
pub const SIG_INEXIGIBLE: &[u8] = b"inexigible";
pub const SIG_HTTPS_PROXY: &[u8] = b"https_proxy";
pub const SIG_AG_PROXY: &[u8] = b"AG_LS_PROXY";

#[derive(Debug, Clone, Default)]
#[allow(dead_code)]
pub struct BinaryStatus {
    pub path: PathBuf,
    pub file_name: String,
    pub ineligible: usize,
    pub inexigible: usize,
    pub https_proxy: usize,
    pub ag_proxy: usize,
    pub is_locked: bool,
}

pub fn find_candidate_binaries() -> Vec<PathBuf> {
    let mut candidates = Vec::new();

    let local_app = std::env::var("LOCALAPPDATA").unwrap_or_default();
    let _app_data = std::env::var("APPDATA").unwrap_or_default();
    let user_profile = std::env::var("USERPROFILE").unwrap_or_default();

    let static_paths = [
        format!(r"{}\Programs\antigravity\resources\bin\language_server.exe", local_app),
        format!(r"{}\Programs\antigravity\resources\bin\agy.exe", local_app),
        format!(r"{}\Programs\Antigravity IDE\resources\app\extensions\antigravity\bin\language_server_windows_x64.exe", local_app),
        format!(r"{}\Programs\Antigravity IDE\resources\bin\language_server.exe", local_app),
        format!(r"{}\.gemini\bin\agy.exe", user_profile),
        format!(r"{}\.gemini\bin\language_server.exe", user_profile),
        format!(r"{}\.antigravity\bin\agy.exe", user_profile),
        format!(r"{}\.antigravity\bin\language_server.exe", user_profile),
    ];

    for p in static_paths {
        if !p.is_empty() {
            let path = PathBuf::from(p);
            if path.is_file() && !candidates.contains(&path) {
                candidates.push(path);
            }
        }
    }

    // Check Scoop apps
    let scoop_dirs = [
        format!(r"{}\scoop\apps\antigravity\current\resources\bin\language_server.exe", user_profile),
        format!(r"{}\scoop\apps\antigravity\current\resources\bin\agy.exe", user_profile),
    ];
    for p in scoop_dirs {
        let path = PathBuf::from(p);
        if path.is_file() && !candidates.contains(&path) {
            candidates.push(path);
        }
    }

    candidates
}

pub fn inspect_binary(path: &Path) -> Result<BinaryStatus> {
    let file_name = path.file_name().unwrap_or_default().to_string_lossy().to_string();
    let bytes = fs::read(path).with_context(|| format!("Failed to read binary {:?}", path))?;

    let ineligible = count_occurrences(&bytes, SIG_INELIGIBLE);
    let inexigible = count_occurrences(&bytes, SIG_INEXIGIBLE);
    let https_proxy = count_occurrences(&bytes, SIG_HTTPS_PROXY);
    let ag_proxy = count_occurrences(&bytes, SIG_AG_PROXY);

    Ok(BinaryStatus {
        path: path.to_path_buf(),
        file_name,
        ineligible,
        inexigible,
        https_proxy,
        ag_proxy,
        is_locked: false,
    })
}

pub fn apply_patch(path: &Path) -> Result<bool> {
    let file_name = path.file_name().unwrap_or_default().to_string_lossy().to_string();

    // Check pending patches first
    let pending_patch = path.with_extension("exe.pending_patch");
    if pending_patch.exists() {
        if let Ok(_) = fs::copy(&pending_patch, path) {
            let _ = fs::remove_file(&pending_patch);
            println!("  {} {}: Applied pending patch successfully.", "[+]".green(), file_name);
        }
    }

    let status = inspect_binary(path)?;
    if status.ineligible == 0 && status.https_proxy == 0 {
        if status.inexigible > 0 {
            println!("  {} {}: Already patched (inexigible: {}, AG_LS_PROXY: {}).", "[i]".cyan(), file_name, status.inexigible, status.ag_proxy);
        } else {
            println!("  {} {}: No target signatures found.", "[?]".yellow(), file_name);
        }
        return Ok(false);
    }

    // Attempt zero-copy in-place memory mapped patch
    let file_res = OpenOptions::new().read(true).write(true).open(path);
    match file_res {
        Ok(file) => {
            let mut mmap = unsafe { MmapMut::map_mut(&file)? };

            let mut inel_replaced = 0;
            let mut proxy_replaced = 0;

            // Replace ineligible -> inexigible (10 bytes -> 10 bytes)
            for i in 0..mmap.len().saturating_sub(SIG_INELIGIBLE.len() - 1) {
                if &mmap[i..i + SIG_INELIGIBLE.len()] == SIG_INELIGIBLE {
                    mmap[i..i + SIG_INELIGIBLE.len()].copy_from_slice(SIG_INEXIGIBLE);
                    inel_replaced += 1;
                }
            }

            // Replace https_proxy -> AG_LS_PROXY (11 bytes -> 11 bytes)
            for i in 0..mmap.len().saturating_sub(SIG_HTTPS_PROXY.len() - 1) {
                if &mmap[i..i + SIG_HTTPS_PROXY.len()] == SIG_HTTPS_PROXY {
                    mmap[i..i + SIG_HTTPS_PROXY.len()].copy_from_slice(SIG_AG_PROXY);
                    proxy_replaced += 1;
                }
            }

            mmap.flush()?;
            println!(
                "  {} {}: Patched successfully (region: {} replaced, proxy-channel: {} replaced).",
                "[+]".green().bold(),
                file_name,
                inel_replaced,
                proxy_replaced
            );
            Ok(true)
        }
        Err(e) => {
            // Handle file lock gracefully
            println!(
                "  {} {}: File is locked by active process ({}). Writing pending patch...",
                "[!]".yellow(),
                file_name,
                e
            );
            let mut bytes = fs::read(path)?;
            replace_slice_inplace(&mut bytes, SIG_INELIGIBLE, SIG_INEXIGIBLE);
            replace_slice_inplace(&mut bytes, SIG_HTTPS_PROXY, SIG_AG_PROXY);
            fs::write(&pending_patch, bytes)?;
            println!("      Pending patch written to: {:?}", pending_patch);
            Ok(false)
        }
    }
}

pub fn rollback_patch(path: &Path) -> Result<bool> {
    let file_name = path.file_name().unwrap_or_default().to_string_lossy().to_string();
    let file_res = OpenOptions::new().read(true).write(true).open(path);

    match file_res {
        Ok(file) => {
            let mut mmap = unsafe { MmapMut::map_mut(&file)? };
            let mut inel_restored = 0;
            let mut proxy_restored = 0;

            for i in 0..mmap.len().saturating_sub(SIG_INEXIGIBLE.len() - 1) {
                if &mmap[i..i + SIG_INEXIGIBLE.len()] == SIG_INEXIGIBLE {
                    mmap[i..i + SIG_INEXIGIBLE.len()].copy_from_slice(SIG_INELIGIBLE);
                    inel_restored += 1;
                }
            }

            for i in 0..mmap.len().saturating_sub(SIG_AG_PROXY.len() - 1) {
                if &mmap[i..i + SIG_AG_PROXY.len()] == SIG_AG_PROXY {
                    mmap[i..i + SIG_AG_PROXY.len()].copy_from_slice(SIG_HTTPS_PROXY);
                    proxy_restored += 1;
                }
            }

            mmap.flush()?;
            println!(
                "  {} {}: Rollback complete (region: {}, proxy-channel: {}).",
                "[+]".green(),
                file_name,
                inel_restored,
                proxy_restored
            );
            Ok(true)
        }
        Err(e) => {
            println!("  {} {}: Cannot rollback, file is locked: {}", "[-]".red(), file_name, e);
            Ok(false)
        }
    }
}

fn count_occurrences(haystack: &[u8], needle: &[u8]) -> usize {
    if needle.is_empty() || haystack.len() < needle.len() {
        return 0;
    }
    haystack.windows(needle.len()).filter(|w| *w == needle).count()
}

fn replace_slice_inplace(data: &mut [u8], needle: &[u8], replacement: &[u8]) {
    assert_eq!(needle.len(), replacement.len());
    let nlen = needle.len();
    for i in 0..data.len().saturating_sub(nlen - 1) {
        if &data[i..i + nlen] == needle {
            data[i..i + nlen].copy_from_slice(replacement);
        }
    }
}
