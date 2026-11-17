use anyhow::{Context, Result};
use colored::*;
use std::fs;
use std::path::PathBuf;

pub const PINNED_DOMAINS: &[&str] = &[
    "cloudcode-pa.googleapis.com",
    "daily-cloudcode-pa.googleapis.com",
    "generativelanguage.googleapis.com",
    "aicode.googleapis.com",
    "antigravity-unleash.goog",
    "cloudaicompanion.googleapis.com",
    "jetski-webchannel.googleapis.com",
    "antigravity.google",
    "alkalimakersuite-pa.googleapis.com",
];

const START_MARKER: &str = "# ANTIGRAVITY_UNLOCKER_START";
const END_MARKER: &str = "# ANTIGRAVITY_UNLOCKER_END";

pub fn get_hosts_path() -> PathBuf {
    if cfg!(target_os = "windows") {
        let sys_root = std::env::var("SystemRoot").unwrap_or_else(|_| "C:\\Windows".to_string());
        PathBuf::from(sys_root).join(r"System32\drivers\etc\hosts")
    } else {
        PathBuf::from("/etc/hosts")
    }
}

pub fn pin_hosts(ip: &str) -> Result<()> {
    let hosts_path = get_hosts_path();
    let content = fs::read_to_string(&hosts_path)
        .with_context(|| format!("Failed to read hosts file: {:?}. (Administrator rights required)", hosts_path))?;

    let cleaned = clean_existing_block(&content);
    let mut new_block = String::new();
    new_block.push_str("\n");
    new_block.push_str(START_MARKER);
    new_block.push_str("\n");
    for domain in PINNED_DOMAINS {
        new_block.push_str(&format!("{:<16} {}\n", ip, domain));
    }
    new_block.push_str(END_MARKER);
    new_block.push_str("\n");

    let final_content = format!("{}{}", cleaned.trim_end(), new_block);
    fs::write(&hosts_path, final_content)
        .with_context(|| format!("Failed to write to hosts file: {:?}. Please run as Administrator.", hosts_path))?;

    println!("  {} Hosts pinned to {} for {} domains.", "[+]".green().bold(), ip, PINNED_DOMAINS.len());
    Ok(())
}

pub fn unpin_hosts() -> Result<()> {
    let hosts_path = get_hosts_path();
    let content = fs::read_to_string(&hosts_path)
        .with_context(|| format!("Failed to read hosts file: {:?}", hosts_path))?;

    let cleaned = clean_existing_block(&content);
    fs::write(&hosts_path, cleaned)
        .with_context(|| format!("Failed to write to hosts file: {:?}. Please run as Administrator.", hosts_path))?;

    println!("  {} Removed Antigravity entries from hosts.", "[+]".green());
    Ok(())
}

pub fn get_pinned_status() -> Result<(usize, Option<String>)> {
    let hosts_path = get_hosts_path();
    if !hosts_path.exists() {
        return Ok((0, None));
    }
    let content = fs::read_to_string(&hosts_path)?;
    let mut count = 0;
    let mut detected_ip = None;

    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('#') || trimmed.is_empty() {
            continue;
        }
        let parts: Vec<&str> = trimmed.split_whitespace().collect();
        if parts.len() >= 2 {
            let ip = parts[0];
            let domain = parts[1];
            if PINNED_DOMAINS.contains(&domain) {
                count += 1;
                if detected_ip.is_none() {
                    detected_ip = Some(ip.to_string());
                }
            }
        }
    }

    Ok((count, detected_ip))
}

fn clean_existing_block(content: &str) -> String {
    let mut result = Vec::new();
    let mut inside_block = false;

    for line in content.lines() {
        if line.contains(START_MARKER) {
            inside_block = true;
            continue;
        }
        if line.contains(END_MARKER) {
            inside_block = false;
            continue;
        }
        if !inside_block {
            result.push(line);
        }
    }
    result.join("\n")
}
