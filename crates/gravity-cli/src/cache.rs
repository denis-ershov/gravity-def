use colored::*;
use std::fs;
use std::path::PathBuf;

pub fn clean_ide_cache() -> (usize, u64) {
    let app_data = std::env::var("APPDATA").unwrap_or_default();
    let user_profile = std::env::var("USERPROFILE").unwrap_or_default();

    let target_dirs = [
        format!(r"{}\Antigravity\CachedData", app_data),
        format!(r"{}\Antigravity\Code Cache\js", app_data),
        format!(r"{}\Antigravity IDE\CachedData", app_data),
        format!(r"{}\Antigravity IDE\Code Cache\js", app_data),
        format!(r"{}\scoop\persist\antigravity\data\CachedData", user_profile),
    ];

    let mut deleted_files = 0;
    let mut freed_bytes = 0;

    for dir_str in target_dirs {
        let dir = PathBuf::from(dir_str);
        if dir.exists() && dir.is_dir() {
            if let Ok(entries) = fs::read_dir(&dir) {
                for entry in entries.flatten() {
                    let path = entry.path();
                    if path.is_file() {
                        if let Ok(meta) = entry.metadata() {
                            freed_bytes += meta.len();
                        }
                        if fs::remove_file(&path).is_ok() {
                            deleted_files += 1;
                        }
                    }
                }
            }
        }
    }

    let mb = freed_bytes as f64 / 1024.0 / 1024.0;
    println!("  {} V8 bytecode cache cleaned: {} files removed ({:.2} MB freed).", "[+]".green(), deleted_files, mb);
    (deleted_files, freed_bytes)
}
