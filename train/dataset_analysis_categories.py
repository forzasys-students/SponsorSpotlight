#!/usr/bin/env python3
"""
YOLO OBB Dataset Analysis Tool (Category Frequency Bar Plot)

This script creates a clean, professional bar plot visualization showing
the frequency distribution of classes by category.

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
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches

# --- Configuration & Style ---
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman'] + plt.rcParams['font.serif']
plt.rcParams['font.size'] = 14
plt.rcParams['axes.labelsize'] = 16
plt.rcParams['axes.titlesize'] = 18
plt.rcParams['xtick.labelsize'] = 20
plt.rcParams['ytick.labelsize'] = 20
plt.rcParams['legend.fontsize'] = 20
plt.rcParams['figure.titlesize'] = 20

# --- Core Functions ---

def load_class_names(class_file):
    """Load class names from file."""
    with open(class_file, 'r') as f:
        class_names = [line.strip() for line in f.readlines()]
    return class_names

def parse_label_file(label_path):
    """Parse YOLO OBB label file to extract class IDs."""
    boxes = []
    if not os.path.exists(label_path):
        return boxes
    
    with open(label_path, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 1:
                class_id = int(parts[0])
                boxes.append({'class_id': class_id})
    return boxes

def analyze_dataset(base_path, class_names):
    """Analyze the entire dataset by combining all splits."""
    splits = ['train', 'val', 'test']
    results = {
        'class_counts': defaultdict(int),
        'total_images': 0,
        'total_boxes': 0,
    }

    image_files = []
    for split in splits:
        split_path = os.path.join(base_path, split, 'images')
        if os.path.exists(split_path):
            image_files.extend([os.path.join(split, 'images', f) for f in os.listdir(split_path) if f.endswith(('.jpg', '.jpeg', '.png'))])

    print(f"Processing {len(image_files)} images across all splits...")
    for img_rel_path in tqdm(image_files):
        img_path = os.path.join(base_path, img_rel_path)
        label_rel_path = img_rel_path.replace('images', 'labels').replace(Path(img_rel_path).suffix, '.txt')
        label_path = os.path.join(base_path, label_rel_path)

        try:
            with Image.open(img_path) as img:
                results['total_images'] += 1
                boxes = parse_label_file(label_path)
                results['total_boxes'] += len(boxes)
                for box in boxes:
                    if box['class_id'] < len(class_names):
                        class_name = class_names[box['class_id']]
                        results['class_counts'][class_name] += 1
        except Exception as e:
            print(f"Error processing {img_path}: {e}")
            continue
            
    return results

# --- Visualization Functions ---

def generate_category_bar_plot(results, class_names, output_dir):
    """
    Generate a clean bar plot showing the distribution of classes by frequency category.
    """
    class_counts = [(name, results['class_counts'][name]) for name in class_names if name in results['class_counts']]
    class_counts.sort(key=lambda x: x[1], reverse=True)
    df = pd.DataFrame(class_counts, columns=['Class', 'Count'])
    
    # Define frequency categories as requested
    categories = [
        (500, float('inf'), "500+"),
        (100, 500, "100-499"),
        (50, 100, "50-99"),
        (10, 50, "10-49"),
        (1, 10, "1-9")
    ]
    
    # Count classes in each category
    category_data = []
    for min_count, max_count, category_name in categories:
        classes_in_category = df[(df['Count'] >= min_count) & (df['Count'] < max_count)]
        count = len(classes_in_category)
        if count > 0:
            category_data.append({
                'Category': category_name,
                'Number of Classes': count,
                'Percentage of Classes': count / len(df) * 100
            })
    
    category_df = pd.DataFrame(category_data)
    
    # Create figure with log scale
    plt.figure(figsize=(14, 9))
    
    # Bar plot showing number of classes per category
    colors = plt.cm.viridis(np.linspace(0.1, 0.9, len(category_df)))
    bars = plt.bar(category_df['Category'], category_df['Number of Classes'], color=colors)
    
    # Add count and percentage labels
    for i, bar in enumerate(bars):
        height = bar.get_height()
        idx = bars.index(bar)
        percentage = category_df['Percentage of Classes'].iloc[idx]
        
        # Position the label lower for the first bar (500+ category)
        if i == 0:  # First bar (assuming it's the 500+ category)
            y_pos = height * 1.3  # Position label at 50% of bar height
            va_align = 'center'
        elif i == 3 or i == 4:
            y_pos = height * 0.7 # Position label at 50% of bar height
            va_align = 'center'
        else:
            y_pos = height + 5
            va_align = 'bottom'
            
        plt.text(bar.get_x() + bar.get_width()/2., y_pos,
                f'{int(height)}\n({percentage:.1f}%)',
                ha='center', va=va_align, fontsize=18, fontweight='bold')

    plt.ylabel('Number of Classes (log scale)', fontsize=24)
    plt.xlabel('Frequency Categories', fontsize=24)
    plt.yscale('log')  # Set log scale for y-axis
    plt.grid(axis='y', alpha=0.3)
    
    # Add dataset statistics
    stats_text = f"Total Classes: {len(df)}\n"
    stats_text += f"Total Objects: {df['Count'].sum():,}\n"
    stats_text += f"Most Frequent: {df['Class'].iloc[0]} ({df['Count'].iloc[0]:,})\n"
    stats_text += f"Least Frequent: {df['Class'].iloc[-1]} ({df['Count'].iloc[-1]:,})"
    
    plt.figtext(0.09, 0.81, stats_text, fontsize=20,
             bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray', boxstyle='round,pad=0.5'))
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'class_frequency_categories.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # Create a second visualization: Top 20 classes
    plt.figure(figsize=(16, 12))
    
    top20 = df.head(20)
    bars = plt.barh(top20['Class'], top20['Count'], color=plt.cm.viridis(np.linspace(0.2, 0.8, len(top20))))
    
    # Add count labels
    for bar in bars:
        width = bar.get_width()
        plt.text(width + width*0.01, bar.get_y() + bar.get_height()/2.,
                f'{int(width):,}',
                ha='left', va='center', fontsize=12, fontweight='bold')
    
    plt.title('Top 20 Most Frequent Classes', fontsize=20, pad=20)
    plt.xlabel('Number of Instances', fontsize=16)
    plt.grid(axis='x', alpha=0.3)
    plt.gca().invert_yaxis()  # To have highest count at the top
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'top20_classes.png'), dpi=300, bbox_inches='tight')
    plt.close()
    
    # Save data as CSV
    df.to_csv(os.path.join(output_dir, 'class_distribution_data.csv'), index=False)
    category_df.to_csv(os.path.join(output_dir, 'category_distribution_data.csv'), index=False)

def main():
    parser = argparse.ArgumentParser(description='Category frequency visualization of YOLO OBB dataset')
    parser.add_argument('--dataset', type=str, default='/Users/mehdi/SponsorSpotlight/train/ready-training',
                        help='Path to dataset directory')
    parser.add_argument('--classes', type=str, default='/Users/mehdi/SponsorSpotlight/inference/classes.txt',
                        help='Path to classes.txt file')
    parser.add_argument('--output', type=str, default='/Users/mehdi/SponsorSpotlight/train/dataset_analysis_results_categories',
                        help='Output directory for category frequency visualization')
    args = parser.parse_args()
    
    os.makedirs(args.output, exist_ok=True)
    
    class_names = load_class_names(args.classes)
    print(f"Loaded {len(class_names)} class names.")
    
    results = analyze_dataset(args.dataset, class_names)
    
    print("Generating category frequency visualization...")
    generate_category_bar_plot(results, class_names, args.output)
    
    print(f"\nCategory frequency visualization saved to {args.output}")

if __name__ == "__main__":
    main()