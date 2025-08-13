#!/usr/bin/env python3
"""
Long-Tail Class Distribution (Rank–Frequency + Pareto Overlay)

This script produces a single, compact, publication-ready plot that shows
ALL classes in a dataset sorted by frequency (rank-frequency plot) with a
cumulative share (Pareto) curve overlaid. Designed to fit a two-column paper.

- X-axis: Class rank (1 = most frequent)
- Left Y-axis (log): Number of instances
- Right Y-axis: Cumulative percentage of instances
- Vertical markers at 80% and 95% cumulative share

Author: Research Department
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from PIL import Image
from pathlib import Path
import argparse
from collections import defaultdict
from tqdm import tqdm

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman'] + plt.rcParams['font.serif']
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 10
plt.rcParams['axes.titlesize'] = 11
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 9


def load_class_names(class_file: str) -> list:
    with open(class_file, 'r') as f:
        return [line.strip() for line in f.readlines()]


def parse_label_file(label_path: str):
    if not os.path.exists(label_path):
        return []
    boxes = []
    with open(label_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 1:
                boxes.append(int(parts[0]))
    return boxes


def analyze_dataset(base_path: str, class_names: list):
    splits = ['train', 'val', 'test']
    class_counts = defaultdict(int)
    total_images = 0

    image_files = []
    for split in splits:
        split_path = os.path.join(base_path, split, 'images')
        if os.path.exists(split_path):
            image_files.extend([os.path.join(split, 'images', f)
                                for f in os.listdir(split_path)
                                if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

    for img_rel in tqdm(image_files, desc='Scanning labels', unit='img'):
        img_path = os.path.join(base_path, img_rel)
        label_rel = img_rel.replace('images', 'labels')
        label_rel = os.path.splitext(label_rel)[0] + '.txt'
        label_path = os.path.join(base_path, label_rel)
        try:
            with Image.open(img_path):
                total_images += 1
                cls_ids = parse_label_file(label_path)
                for cid in cls_ids:
                    if 0 <= cid < len(class_names):
                        class_counts[cid] += 1
        except Exception:
            continue

    # Build DataFrame (only classes with at least 1 instance)
    data = [(cid, class_names[cid], cnt) for cid, cnt in class_counts.items() if cnt > 0]
    df = pd.DataFrame(data, columns=['class_id', 'class_name', 'count'])
    df = df.sort_values('count', ascending=False).reset_index(drop=True)
    if df.empty:
        raise RuntimeError('No labeled instances found in the dataset.')

    # Rank and cumulative share
    df['rank'] = np.arange(1, len(df) + 1)
    df['cum'] = df['count'].cumsum()
    total = df['count'].sum()
    df['cum_pct'] = 100.0 * df['cum'] / total

    # Threshold indices
    idx80 = int(np.searchsorted(df['cum_pct'].values, 80.0))  # 0-based index
    idx95 = int(np.searchsorted(df['cum_pct'].values, 95.0))

    return df, total, idx80, idx95


def plot_rank_pareto(df: pd.DataFrame, total: int, idx80: int, idx95: int, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)

    # Figure sized for 2-column paper (~7.2in wide x ~3.6in tall)
    fig, ax1 = plt.subplots(figsize=(7.2, 3.6), dpi=300)

    # Left y-axis: rank-frequency (log scale)
    ax1.plot(df['rank'], df['count'], linewidth=1.0, color='#1f77b4', alpha=0.9)
    ax1.scatter(df['rank'], df['count'], s=6, color='#1f77b4', alpha=0.6)
    ax1.set_yscale('log')
    ax1.set_xlabel('Class rank (1 = most frequent)')
    ax1.set_ylabel('Instances (log scale)')

    # Right y-axis: cumulative percentage (Pareto)
    ax2 = ax1.twinx()
    ax2.plot(df['rank'], df['cum_pct'], color='#d62728', linewidth=1.2)
    ax2.set_ylabel('Cumulative %')
    ax2.set_ylim(0, 100)

    # 80% and 95% markers
    for idx, pct, color in [(idx80, 80, '#2ca02c'), (idx95, 95, '#9467bd')]:
        x_rank = df['rank'].iloc[idx] if idx < len(df) else df['rank'].iloc[-1]
        ax1.axvline(x=x_rank, color=color, linestyle='--', linewidth=0.8)
        ax2.axhline(y=pct, color=color, linestyle='--', linewidth=0.8)
        ax2.annotate(f'{pct}% at class #{x_rank}',
                     xy=(x_rank, pct), xytext=(x_rank, pct + 6),
                     textcoords='data', fontsize=8, color=color,
                     arrowprops=dict(arrowstyle='-', color=color, lw=0.8))

    # Ticks and grid
    ax1.grid(True, which='both', axis='both', alpha=0.25)

    # Tight layout and save
    plt.tight_layout()
    out_path = os.path.join(out_dir, 'longtail_rank_pareto.png')
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close()

    # Also save CSV for reproducibility
    df[['rank', 'class_id', 'class_name', 'count', 'cum_pct']].to_csv(
        os.path.join(out_dir, 'longtail_rank_data.csv'), index=False
    )


def main():
    parser = argparse.ArgumentParser(description='Long-tail rank-frequency plot with Pareto overlay')
    parser.add_argument('--dataset', type=str, default='/Users/mehdi/SponsorSpotlight/train/ready-training',
                        help='Path to dataset root (with train/val/test)')
    parser.add_argument('--classes', type=str, default='/Users/mehdi/SponsorSpotlight/inference/classes.txt',
                        help='Path to classes.txt')
    parser.add_argument('--output', type=str, default='/Users/mehdi/SponsorSpotlight/train/dataset_analysis_results_rank',
                        help='Output directory')
    args = parser.parse_args()

    class_names = load_class_names(args.classes)
    df, total, idx80, idx95 = analyze_dataset(args.dataset, class_names)
    plot_rank_pareto(df, total, idx80, idx95, args.output)
    
    print(f'Plot saved to: {args.output}/longtail_rank_pareto.png')
    print(f'Total classes with instances: {len(df)} | Total objects: {total:,}')
    print(f'80% cumulative by class #{df["rank"].iloc[idx80] if idx80 < len(df) else df["rank"].iloc[-1]}')
    print(f'95% cumulative by class #{df["rank"].iloc[idx95] if idx95 < len(df) else df["rank"].iloc[-1]}')


if __name__ == '__main__':
    main()
