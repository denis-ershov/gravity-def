use colored::*;
use std::net::SocketAddr;
use std::time::{Duration, Instant};
use tokio::net::TcpStream;
use tokio::time::timeout;

pub const PROXY_CANDIDATES: &[(&str, &str)] = &[
    ("45.88.174.252",  "DE - Frankfurt (Fast Anycast)"),
    ("94.130.180.225", "DE - Hetzner Dedicated"),
    ("178.62.224.238", "NL - Amsterdam DigitalOcean"),
    ("188.166.114.80", "UK - London"),
    ("195.201.201.32", "FI - Helsinki"),
];

#[derive(Debug, Clone)]
pub struct BenchmarkResult {
    pub ip: String,
    pub description: String,
    pub latency_ms: Option<u128>,
    pub is_alive: bool,
}

pub async fn probe_proxy(ip: &str, desc: &str, port: u16, timeout_duration: Duration) -> BenchmarkResult {
    let addr_str = format!("{}:{}", ip, port);
    let addr: SocketAddr = match addr_str.parse() {
        Ok(a) => a,
        Err(_) => {
            return BenchmarkResult {
                ip: ip.to_string(),
                description: desc.to_string(),
                latency_ms: None,
                is_alive: false,
            }
        }
    };

    let start = Instant::now();
    match timeout(timeout_duration, TcpStream::connect(&addr)).await {
        Ok(Ok(_stream)) => {
            let elapsed = start.elapsed().as_millis();
            BenchmarkResult {
                ip: ip.to_string(),
                description: desc.to_string(),
                latency_ms: Some(elapsed),
                is_alive: true,
            }
        }
        _ => BenchmarkResult {
            ip: ip.to_string(),
            description: desc.to_string(),
            latency_ms: None,
            is_alive: false,
        },
    }
}

pub async fn find_fastest_proxy() -> Option<BenchmarkResult> {
    println!("{} Benchmarking {} proxy candidates concurrently via Tokio...", "[*]".cyan(), PROXY_CANDIDATES.len());

    let mut tasks = Vec::new();
    for (ip, desc) in PROXY_CANDIDATES {
        let ip_c = ip.to_string();
        let desc_c = desc.to_string();
        tasks.push(tokio::spawn(async move {
            probe_proxy(&ip_c, &desc_c, 443, Duration::from_millis(2500)).await
        }));
    }

    let mut results = Vec::new();
    for task in tasks {
        if let Ok(res) = task.await {
            results.push(res);
        }
    }

    results.sort_by(|a, b| {
        match (a.latency_ms, b.latency_ms) {
            (Some(la), Some(lb)) => la.cmp(&lb),
            (Some(_), None) => std::cmp::Ordering::Less,
            (None, Some(_)) => std::cmp::Ordering::Greater,
            (None, None) => std::cmp::Ordering::Equal,
        }
    });

    for r in &results {
        if let Some(lat) = r.latency_ms {
            println!("  {} {:<16} {:<32} ({} ms)", "[+]".green(), r.ip, r.description, lat);
        } else {
            println!("  {} {:<16} {:<32} (Timeout)", "[-]".red(), r.ip, r.description);
        }
    }

    results.into_iter().find(|r| r.is_alive)
}
