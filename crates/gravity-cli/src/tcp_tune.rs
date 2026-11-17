use anyhow::Result;
use colored::*;
use std::process::Command;

pub fn tune_tcp_stack() -> Result<()> {
    if !cfg!(target_os = "windows") {
        println!("  {} TCP tuning is only applicable on Windows.", "[i]".cyan());
        return Ok(());
    }

    let settings = [
        ("autotuninglevel", "normal"),
        ("fastopen", "enabled"),
        ("rss", "enabled"),
        ("hystart", "enabled"),
        ("prr", "enabled"),
        ("timestamps", "allowed"),
        ("ecncapability", "enabled"),
    ];

    println!("{} Optimizing Windows TCP/IP stack for AI streaming...", "[*]".cyan());
    for (param, val) in settings {
        let arg = format!("{}={}", param, val);
        let res = Command::new("netsh")
            .args(&["int", "tcp", "set", "global", &arg])
            .output();

        match res {
            Ok(out) if out.status.success() => {
                println!("  {} set {} = {}", "[+]".green(), param, val);
            }
            _ => {
                println!("  {} set {} = {} (Requires Admin)", "[!]".yellow(), param, val);
            }
        }
    }

    Ok(())
}
