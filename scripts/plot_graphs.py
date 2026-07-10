# /// script
# dependencies = [
#     "matplotlib",
#     "pandas",
# ]
# ///

import argparse
import glob
import os
import sys

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def parse_time(val):
    val = str(val)
    if val in {'nan', 'NaN'}:
        return np.nan
    if 'ms' in val:
        return float(val.replace(' ms', '').strip())
    if 's' in val:
        return float(val.replace(' s', '').strip()) * 1000
    try:
        return float(val)
    except ValueError:
        return np.nan


def read_csv_with_time(path):
    df = pd.read_csv(path)
    if 'Time' not in df.columns:
        raise ValueError(f"File {path} does not contain a 'Time' column")
    df['Time'] = pd.to_datetime(df['Time'])
    df.set_index('Time', inplace=True)
    for col in df.columns:
        df[col] = df[col].apply(parse_time)
    return df


def draw_combined_backgrounds(ax, rr_series, pq_series):
    rr_times = rr_series.dropna().index
    pq_times = pq_series.dropna().index
    if rr_times.empty and pq_times.empty: return
    
    all_times = sorted(list(set(rr_times) | set(pq_times)))
    
    blocks = []
    start_t = all_times[0]
    current_algo = 'rr' if start_t in rr_times else 'pq'
    
    for i in range(len(all_times)-1):
        t1 = all_times[i]
        t2 = all_times[i+1]
        
        algo1 = 'rr' if t1 in rr_times else 'pq'
        algo2 = 'rr' if t2 in rr_times else 'pq'
        
        gap = (t2 - t1).total_seconds()
        
        if gap > 60:
            blocks.append((current_algo, start_t, t1))
            start_t = t2
            current_algo = algo2
        elif algo1 != algo2:
            midpoint = t1 + (t2 - t1) / 2
            blocks.append((current_algo, start_t, midpoint))
            start_t = midpoint
            current_algo = algo2
            
    blocks.append((current_algo, start_t, all_times[-1]))
    
    if blocks:
        ax.axvline(blocks[0][1], color='black', linestyle='-', alpha=0.6, linewidth=2.0)
        for i, (algo, b_start, b_end) in enumerate(blocks):
            color = '#ff7f0e' if algo == 'rr' else '#1f77b4'
            ax.axvspan(b_start, b_end, facecolor=color, alpha=0.08)
            
            if algo == 'pq':
                ax.axvline(b_end, color='black', linestyle='-', alpha=0.6, linewidth=2.0)
            else:
                ax.axvline(b_end, color='gray', linestyle='--', alpha=0.6, linewidth=1.2)

        loads = ["75%", "83%", "93%", "103%", "114%", "127%", "141%", "157%", "174%"]
        pair_idx = 0
        i = 0
        while i < len(blocks) - 1:
            if blocks[i][0] == 'rr' and blocks[i+1][0] == 'pq':
                if pair_idx < len(loads):
                    mid_time = blocks[i][1] + (blocks[i+1][2] - blocks[i][1]) / 2
                    ax.text(mid_time, 0.98, f"{loads[pair_idx]} CPU", transform=ax.get_xaxis_transform(),
                            ha='center', va='top', fontsize=10, fontweight='bold',
                            bbox=dict(facecolor='white', alpha=0.9, edgecolor='gray', boxstyle='round,pad=0.2'))
                    pair_idx += 1
                i += 2
            else:
                i += 1


def plot_latency(path, output_path):
    df_lat = read_csv_with_time(path)
    
    if 'roundrobin p50' in df_lat.columns:
        rr_notna = df_lat['roundrobin p50'].notna()
        streak = rr_notna.rolling(5).sum()
        if (streak == 5).any():
            import numpy as np
            idx = np.where(streak == 5)[0][0] - 4
            first_rr_time = df_lat.index[idx]
            df_lat = df_lat[df_lat.index >= first_rr_time]

    fig, ax = plt.subplots(figsize=(12, 6))

    c_p50 = '#2ca02c'
    c_p90 = '#1f77b4'
    c_p99 = '#daa520'
    c_p999 = '#d62728'

    if 'prequal p50' in df_lat.columns: 
        ax.plot(df_lat.index, df_lat['prequal p50'], label='p50', color=c_p50, linewidth=1.2)
        ax.plot(df_lat.index, df_lat['prequal p90'], label='p90', color=c_p90, linewidth=1.2)
        ax.plot(df_lat.index, df_lat['prequal p99'], label='p99', color=c_p99, linewidth=1.2)
        ax.plot(df_lat.index, df_lat['prequal p99.9'], label='p99.9', color=c_p999, linewidth=1.2)

    if 'roundrobin p50' in df_lat.columns: 
        ax.plot(df_lat.index, df_lat['roundrobin p50'], color=c_p50, linewidth=1.2)
        ax.plot(df_lat.index, df_lat['roundrobin p90'], color=c_p90, linewidth=1.2)
        ax.plot(df_lat.index, df_lat['roundrobin p99'], color=c_p99, linewidth=1.2)
        ax.plot(df_lat.index, df_lat['roundrobin p99.9'], color=c_p999, linewidth=1.2)

    rr_lat = df_lat['roundrobin p50'] if 'roundrobin p50' in df_lat.columns else pd.Series(dtype=float)
    pq_lat = df_lat['prequal p50'] if 'prequal p50' in df_lat.columns else pd.Series(dtype=float)
    draw_combined_backgrounds(ax, rr_lat, pq_lat)

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.set_title(f"Request Latency - {os.path.basename(path)}", fontsize=14, fontweight='bold')
    ax.set_ylabel('Latency (ms)', fontsize=12)
    ax.set_xlabel('Time', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_rif(path, output_path):
    df_rif = read_csv_with_time(path)
    cols = list(df_rif.columns)
    if len(cols) < 6:
        raise ValueError(f"File {path} does not contain enough RIF columns")

    cols_prequal = cols[0:3]
    cols_rr = cols[3:6]

    rr_active_temp = df_rif[cols_rr].sum(axis=1) > 0
    streak = rr_active_temp.rolling(5).sum()
    if (streak == 5).any():
        import numpy as np
        idx = np.where(streak == 5)[0][0] - 4
        first_rr_time = df_rif.index[idx]
        df_rif = df_rif[df_rif.index >= first_rr_time]

    fig, ax = plt.subplots(figsize=(12, 6))
    colors_rr = ['#d62728', '#ff7f0e', '#bcbd22']
    colors_prequal = ['#1f77b4', '#17becf', '#2ca02c']

    rr_active = df_rif[cols_rr].sum(axis=1) > 0
    pq_active = df_rif[cols_prequal].sum(axis=1) > 0

    for i in range(3):
        data = df_rif[cols_rr[i]]
        ax.plot(data.index, data, label=f'RR - Server {i+1}', color=colors_rr[i], linewidth=1.0, alpha=0.9)

    for i in range(3):
        data = df_rif[cols_prequal[i]]
        ax.plot(data.index, data, label=f'Prequal - Server {i+1}', color=colors_prequal[i], linewidth=1.2)

    rr_rif = df_rif[cols_rr[0]].where(rr_active).dropna()
    pq_rif = df_rif[cols_prequal[0]].where(pq_active).dropna()
    draw_combined_backgrounds(ax, rr_rif, pq_rif)

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.set_title(f"Requests In Flight (RIF) - {os.path.basename(path)}", fontsize=14, fontweight='bold')
    ax.set_ylabel('Requests in flight (RIF)', fontsize=12)
    ax.set_xlabel('Time', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)


def collect_input_files(files):
    if files:
        resolved = []
        for path in files:
            if not os.path.isabs(path):
                path = os.path.abspath(path)
            if not os.path.isfile(path):
                raise FileNotFoundError(f"Input file not found: {path}")
            resolved.append(path)
        return resolved

    metrics_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'metrics'))
    if not os.path.isdir(metrics_dir):
        raise FileNotFoundError(f"Default metrics directory not found: {metrics_dir}")

    all_files = sorted(glob.glob(os.path.join(metrics_dir, '**', '*.csv'), recursive=True))
    return [path for path in all_files if os.path.isfile(path)]


def classify_files(paths):
    latency_files = []
    rif_files = []
    other_files = []

    for path in paths:
        name = os.path.basename(path).lower()
        if not name.endswith('.csv'):
            continue
        if 'latency' in name:
            latency_files.append(path)
        elif 'rif' in name:
            rif_files.append(path)
        else:
            other_files.append(path)

    return latency_files, rif_files, other_files


def build_output_path(input_path, suffix):
    stem = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(output_dir, f"{stem}_{suffix}.png")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Plot latency and RIF files.')
    parser.add_argument('files', nargs='*', help='Input files to plot. If omitted, files are read recursively from the metrics directory.')
    args = parser.parse_args()

    script_dir = os.path.dirname(__file__)
    output_dir = os.path.abspath(os.path.join(script_dir, '..', 'results'))
    os.makedirs(output_dir, exist_ok=True)

    input_paths = collect_input_files(args.files)
    latency_files, rif_files, other_files = classify_files(input_paths)

    if other_files:
        print(f"Skipping files that cannot be classified as latency or RIF: {other_files}")

    if not latency_files and not rif_files:
        print('No latency or RIF files found to plot.')
        sys.exit(1)

    for path in latency_files:
        print(f"Generating latency plot from {path}...")
        output_path = build_output_path(path, 'latency_plot')
        plot_latency(path, output_path)
        print(f"Saved: {output_path}")

    for path in rif_files:
        print(f"Generating RIF plot from {path}...")
        output_path = build_output_path(path, 'rif_plot')
        plot_rif(path, output_path)
        print(f"Saved: {output_path}")

    print('Script completed successfully!')