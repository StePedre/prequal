import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Function to clean data (Grafana sometimes exports milliseconds as "59.2 ms" or "1.2 s")
def parse_time(val):
    val = str(val)
    if val == 'nan' or val == 'NaN':
        return np.nan
    if 'ms' in val:
        return float(val.replace(' ms', ''))
    elif 's' in val:
        return float(val.replace(' s', '')) * 1000
    try:
        return float(val)
    except:
        return np.nan


def load_csv(path: Path):
    df = pd.read_csv(path)
    df['Time'] = pd.to_datetime(df['Time'])
    df.set_index('Time', inplace=True)
    for col in df.columns:
        df[col] = df[col].apply(parse_time)
    return df


def plot_latency(csv_path: Path, output_dir: Path):
    print(f"Generating latency plot from {csv_path.name}...")
    df_lat = load_csv(csv_path)

    plt.figure(figsize=(12, 6))
    plt.plot(df_lat.index, df_lat['prequal p50'], label='Prequal p50', color='#2ca02c', linestyle='--')
    plt.plot(df_lat.index, df_lat['roundrobin p50'], label='RR p50', color='#d62728', linestyle='--')
    plt.plot(df_lat.index, df_lat['prequal p99'], label='Prequal p99', color='#2ca02c', linewidth=2.5)
    plt.plot(df_lat.index, df_lat['roundrobin p99'], label='RR p99', color='#d62728', linewidth=2.5)

    plt.title('Request Latency (p50 vs p99) - Prequal vs Round-Robin', fontsize=14, fontweight='bold')
    plt.ylabel('Latency (ms)', fontsize=12)
    plt.xlabel('Time', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend(loc='upper left')
    plt.tight_layout()

    output_path = output_dir / f"custom_latency_plot_{csv_path.stem}.png"
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Saved: {output_path}")


def plot_rif(csv_path: Path, output_dir: Path):
    print(f"Generating RIF plot from {csv_path.name}...")
    df_rif = load_csv(csv_path)

    cols = df_rif.columns
    group1 = cols[0:3]
    group2 = cols[3:6]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharey=True)

    ax1.plot(df_rif.index, df_rif[group1[0]], label='Server 1 (60% load)', color='#ff7f0e')
    ax1.plot(df_rif.index, df_rif[group1[1]], label='Server 2 (60% load)', color='#d62728')
    ax1.plot(df_rif.index, df_rif[group1[2]], label='Server 3 (Idle)', color='#1f77b4')
    ax1.set_title('Requests In Flight - Group 1 (Identify whether it is RR or Prequal!)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Requests in queue (RIF)')
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    ax2.plot(df_rif.index, df_rif[group2[0]], label='Server 1 (60% load)', color='#ff7f0e')
    ax2.plot(df_rif.index, df_rif[group2[1]], label='Server 2 (60% load)', color='#d62728')
    ax2.plot(df_rif.index, df_rif[group2[2]], label='Server 3 (Idle)', color='#1f77b4')
    ax2.set_title('Requests In Flight - Group 2 (Identify whether it is RR or Prequal!)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Requests in queue (RIF)')
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    plt.tight_layout()
    output_path = output_dir / f"custom_rif_plot_{csv_path.stem}.png"
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Saved: {output_path}")


def main():
    script_dir = Path(__file__).resolve().parent
    base_dir = script_dir.parent / 'metrics' / 'base'

    if not base_dir.exists():
        raise FileNotFoundError(f"Metrics base directory not found: {base_dir}")

    latency_files = sorted(base_dir.glob('*latency*.csv'))
    rif_files = sorted(base_dir.glob('*RIF*.csv'))

    if not latency_files:
        print(f"No latency CSV files found in {base_dir}")
    else:
        for csv_path in latency_files:
            plot_latency(csv_path, script_dir)

    if not rif_files:
        print(f"No RIF CSV files found in {base_dir}")
    else:
        for csv_path in rif_files:
            plot_rif(csv_path, script_dir)

    print('Script finished successfully!')


if __name__ == '__main__':
    main()
