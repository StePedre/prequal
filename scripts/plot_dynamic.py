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


def draw_combined_backgrounds(ax, rr_series, pq_series, args=None, df_index=None):
    if args and (args.start or args.event1 or args.split or args.event2 or args.end):
        base_date = df_index[0].strftime('%Y-%m-%d')
        def parse_arg_time(time_str):
            if not time_str: return None
            return pd.to_datetime(f"{base_date} {time_str}")
            
        start_t = parse_arg_time(args.start) if args.start else df_index[0]
        event1_t = parse_arg_time(args.event1)
        split_t = parse_arg_time(args.split)
        event2_t = parse_arg_time(args.event2)
        end_t = parse_arg_time(args.end) if args.end else df_index[-1]
        
        if split_t:
            ax.axvspan(start_t, split_t, facecolor='#ff7f0e', alpha=0.08)
            ax.axvspan(split_t, end_t, facecolor='#1f77b4', alpha=0.08)
            ax.axvline(split_t, color='black', linestyle='-', linewidth=2.0, alpha=0.6)
        else:
            # Fallback for backgrounds se non metti lo split
            ax.axvspan(start_t, end_t, facecolor='#eeeeee', alpha=0.3)
            
        if event1_t:
            ax.axvline(event1_t, color='red', linestyle='--', alpha=0.8, linewidth=2.0)
        if event2_t:
            ax.axvline(event2_t, color='red', linestyle='--', alpha=0.8, linewidth=2.0)
            
        return start_t, end_t

    rr_times = rr_series.dropna().index
    pq_times = pq_series.dropna().index
    
    if rr_times.empty or pq_times.empty:
        return None, None
        
    rr_start = rr_times[0]
    rr_end = rr_times[-1]
    
    pq_times = pq_times[pq_times > rr_start]
    if pq_times.empty:
        return df_index[0], df_index[-1]
        
    pq_start = pq_times[0]
    pq_end = pq_times[-1]
    
    midpoint = rr_end + (pq_start - rr_end) / 2
    
    ax.axvspan(rr_start, midpoint, facecolor='#ff7f0e', alpha=0.08)
    ax.axvspan(midpoint, pq_end, facecolor='#1f77b4', alpha=0.08)
    ax.axvline(midpoint, color='black', linestyle='-', linewidth=2.0, alpha=0.6)
            
    rr_event = rr_start + pd.Timedelta(seconds=120)
    if rr_event < midpoint:
        ax.axvline(rr_event, color='red', linestyle='--', alpha=0.8, linewidth=2.0)
                
    pq_event = pq_start + pd.Timedelta(seconds=120)
    if pq_event < pq_end:
        ax.axvline(pq_event, color='red', linestyle='--', alpha=0.8, linewidth=2.0)
                
    return rr_start, pq_end


def plot_latency(path, output_path, args=None):
    df_lat = read_csv_with_time(path)
    
    is_manual = args and (args.start or args.event1 or args.split or args.event2 or args.end)
    
    if is_manual:
        base_date = df_lat.index[0].strftime('%Y-%m-%d')
        if args.start:
            df_lat = df_lat[df_lat.index >= pd.to_datetime(f"{base_date} {args.start}")]
        if args.end:
            df_lat = df_lat[df_lat.index <= pd.to_datetime(f"{base_date} {args.end}")]
    else:
        if 'roundrobin p50' in df_lat.columns:
            rr_notna = df_lat['roundrobin p50'].notna()
            streak = rr_notna.rolling(5).sum()
            if (streak == 5).any():
                import numpy as np
                idx = np.where(streak == 5)[0][0] - 4
                first_rr_time = df_lat.index[idx]
                df_lat = df_lat[df_lat.index >= first_rr_time]
                
        if 'prequal p50' in df_lat.columns:
            pq_notna = df_lat['prequal p50'].notna()
            if pq_notna.any():
                import numpy as np
                last_pq_time = df_lat.index[np.where(pq_notna)[0][-1]]
                df_lat = df_lat[df_lat.index <= last_pq_time]

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
    
    if not is_manual:
        if not pq_lat.dropna().empty and not rr_lat.dropna().empty:
            first_rr_time = rr_lat.dropna().index[0]
            pq_after_rr = pq_lat.dropna()[pq_lat.dropna().index > first_rr_time]
            if not pq_after_rr.empty:
                pq_start_time = pq_after_rr.index[0]
                rr_lat = rr_lat[rr_lat.index < pq_start_time]

    start_t, end_t = draw_combined_backgrounds(ax, rr_lat, pq_lat, args=args, df_index=df_lat.index)
    
    if start_t is not None and end_t is not None:
        ax.set_xlim(left=start_t, right=end_t)

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.set_ylabel('Latency (ms)', fontsize=12)
    ax.set_xlabel('Time', fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_rif(path, output_path, args=None):
    df_rif = read_csv_with_time(path)
    cols = list(df_rif.columns)
    if len(cols) < 6: return
    
    is_manual = args and (args.start or args.event1 or args.split or args.event2 or args.end)
    cols_prequal = cols[0:3]
    cols_rr = cols[3:6]

    if is_manual:
        base_date = df_rif.index[0].strftime('%Y-%m-%d')
        if args.start:
            df_rif = df_rif[df_rif.index >= pd.to_datetime(f"{base_date} {args.start}")]
        if args.end:
            df_rif = df_rif[df_rif.index <= pd.to_datetime(f"{base_date} {args.end}")]
    else:
        rr_active_temp = df_rif[cols_rr].sum(axis=1) > 0
        streak = rr_active_temp.rolling(5).sum()
        if (streak == 5).any():
            import numpy as np
            idx = np.where(streak == 5)[0][0] - 4
            first_rr_time = df_rif.index[idx]
            df_rif = df_rif[df_rif.index >= first_rr_time]
            
        pq_active_temp = df_rif[cols_prequal].sum(axis=1) > 0
        if pq_active_temp.any():
            import numpy as np
            last_pq_time = df_rif.index[np.where(pq_active_temp)[0][-1]]
            df_rif = df_rif[df_rif.index <= last_pq_time]

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
    start_t, end_t = draw_combined_backgrounds(ax, rr_rif, pq_rif, args=args, df_index=df_rif.index)
    
    if start_t is not None and end_t is not None:
        ax.set_xlim(left=start_t, right=end_t)

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
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
    parser.add_argument('--start', help='Start time of the graph (HH:MM:SS)')
    parser.add_argument('--event1', help='Time of the first kill event (HH:MM:SS)')
    parser.add_argument('--split', help='Time of the black separator line (HH:MM:SS)')
    parser.add_argument('--event2', help='Time of the second kill event (HH:MM:SS)')
    parser.add_argument('--end', help='End time of the graph (HH:MM:SS)')
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
        plot_latency(path, output_path, args)
        print(f"Saved: {output_path}")

    for path in rif_files:
        print(f"Generating RIF plot from {path}...")
        output_path = build_output_path(path, 'rif_plot')
        plot_rif(path, output_path, args)
        print(f"Saved: {output_path}")

    print('Script completed successfully!')