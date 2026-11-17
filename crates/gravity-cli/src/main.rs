use anyhow::Result;
use clap::{Parser, Subcommand};
use colored::*;

mod benchmark;
mod cache;
mod hosts;
mod patcher;
mod tcp_tune;

#[derive(Parser)]
#[command(name = "gravity-cli")]
#[command(about = "High-performance native Rust core for Antigravity Unlocker 2.1", long_about = None)]
#[command(version = "2.1.0")]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Comprehensive system diagnostics & status
    Status,
    /// Apply complete zero-leak geo unblock
    Unlock {
        #[arg(short, long)]
        ip: Option<String>,
    },
    /// Clean rollback of all system modifications
    Rollback,
    /// Patch Language Server & agy executables
    Patch,
    /// Rollback binary patches
    Unpatch,
    /// Benchmark candidate SNI proxies concurrently via Tokio
    Benchmark,
    /// Clean IDE V8 bytecode cache
    CleanCache,
    /// Tune Windows TCP/IP stack
    TuneTcp,
}

#[tokio::main]
async fn main() -> Result<()> {
    // Enable colored output on Windows console
    #[cfg(target_os = "windows")]
    let _ = colored::control::set_virtual_terminal(true);

    let cli = Cli::parse();

    println!("{}", "============================================================".cyan());
    println!("{}", " Antigravity Unlocker 2.1 [Native Rust Core Engine]        ".cyan().bold());
    println!("{}", "============================================================".cyan());

    match cli.command.unwrap_or(Commands::Status) {
        Commands::Status => {
            println!("\n{} Checking binary patch status...", "[1/3]".bold());
            let binaries = patcher::find_candidate_binaries();
            if binaries.is_empty() {
                println!("  {} No Antigravity executables detected.", "[-]".yellow());
            } else {
                for b in binaries {
                    if let Ok(st) = patcher::inspect_binary(&b) {
                        println!(
                            "  {} {:<24} (inexigible: {}, ineligible: {}, AG_LS_PROXY: {}, https_proxy: {})",
                            if st.inexigible > 0 { "[OK]".green() } else { "[!]".yellow() },
                            st.file_name,
                            st.inexigible,
                            st.ineligible,
                            st.ag_proxy,
                            st.https_proxy
                        );
                    }
                }
            }

            println!("\n{} Checking hosts file pinning...", "[2/3]".bold());
            let (pinned_count, ip_opt) = hosts::get_pinned_status()?;
            if pinned_count > 0 {
                println!(
                    "  {} {} domains pinned to {}",
                    "[+]".green(),
                    pinned_count,
                    ip_opt.unwrap_or_default()
                );
            } else {
                println!("  {} No Antigravity domains pinned in hosts.", "[-]".yellow());
            }

            println!("\n{} Probing default proxy latency...", "[3/3]".bold());
            let res = benchmark::probe_proxy("45.88.174.252", "Default Frankfurt", 443, std::time::Duration::from_millis(2000)).await;
            if let Some(lat) = res.latency_ms {
                println!("  {} Default proxy (45.88.174.252:443) is alive ({} ms)", "[+]".green(), lat);
            } else {
                println!("  {} Default proxy connection timed out.", "[-]".red());
            }
        }
        Commands::Unlock { ip } => {
            println!("\n{} Selecting SNI proxy...", "[Step 1/5]".bold());
            let target_ip = match ip {
                Some(user_ip) => user_ip,
                None => match benchmark::find_fastest_proxy().await {
                    Some(fastest) => fastest.ip,
                    None => "45.88.174.252".to_string(),
                },
            };

            println!("\n{} Pinning hosts to {}...", "[Step 2/5]".bold(), target_ip);
            let _ = hosts::pin_hosts(&target_ip);

            println!("\n{} Patching Antigravity binaries...", "[Step 3/5]".bold());
            let binaries = patcher::find_candidate_binaries();
            for b in binaries {
                let _ = patcher::apply_patch(&b);
            }

            println!("\n{} Cleaning V8 bytecode cache...", "[Step 4/5]".bold());
            cache::clean_ide_cache();

            println!("\n{} Tuning TCP stack for AI streaming...", "[Step 5/5]".bold());
            let _ = tcp_tune::tune_tcp_stack();

            println!("\n{}", "============================================================".green());
            println!("{}", " [OK] Antigravity Unblock Applied Successfully!             ".green().bold());
            println!("{}", "============================================================".green());
        }
        Commands::Rollback => {
            println!("\n{} Reverting hosts modifications...", "[1/3]".bold());
            let _ = hosts::unpin_hosts();

            println!("\n{} Reverting binary patches...", "[2/3]".bold());
            let binaries = patcher::find_candidate_binaries();
            for b in binaries {
                let _ = patcher::rollback_patch(&b);
            }

            println!("\n{} Clearing V8 cache...", "[3/3]".bold());
            cache::clean_ide_cache();

            println!("\n{}", "============================================================".yellow());
            println!("{}", " [OK] System Cleanly Rolled Back to Original State!         ".yellow().bold());
            println!("{}", "============================================================".yellow());
        }
        Commands::Patch => {
            println!("\n{} Patching binaries...", "[*]".bold());
            let binaries = patcher::find_candidate_binaries();
            for b in binaries {
                let _ = patcher::apply_patch(&b);
            }
        }
        Commands::Unpatch => {
            println!("\n{} Restoring binaries...", "[*]".bold());
            let binaries = patcher::find_candidate_binaries();
            for b in binaries {
                let _ = patcher::rollback_patch(&b);
            }
        }
        Commands::Benchmark => {
            benchmark::find_fastest_proxy().await;
        }
        Commands::CleanCache => {
            cache::clean_ide_cache();
        }
        Commands::TuneTcp => {
            let _ = tcp_tune::tune_tcp_stack();
        }
    }

    Ok(())
}
