import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['font.size'] = 11
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 12

# === DATA ===
gpus = ['A100\nSXM4\n80GB', 'A100\nPCIe\n80GB', 'H100\nSXM5\n80GB', 'H100\nPCIe\n80GB',
        'H200\nSXM\n141GB', 'B200\nSXM\n192GB', 'B300\nSXM\n288GB', 'RTX PRO\n6000 BW\n96GB',
        'L40S\n48GB', 'MI300X\n192GB', 'MI325X\n256GB']

gpu_labels_short = ['A100\nSXM4', 'A100\nPCIe', 'H100\nSXM5', 'H100\nPCIe',
                    'H200\nSXM', 'B200\nSXM', 'B300\nSXM', 'RTX PRO\n6000 BW',
                    'L40S', 'MI300X', 'MI325X']

# Compute
fp16_tflops = [312, 312, 989, 756, 989, 2250, 3500, 500, 733, 1307.4, 1307.4]
fp8_tflops = [0, 0, 1979, 1513, 1979, 4500, 7000, 1010, 1466, 2614.9, 2614.9]
fp32_tflops = [19.5, 19.5, 67, 51, 67, 75, 75, 126, 91.1, 163.4, 163.4]
int8_tops = [312, 312, 1979, 1513, 1979, 4500, 7000, 1010, 733, 2614.9, 2614.9]
fp4_tflops = [0, 0, 0, 0, 0, 9000, 15000, 2020, 0, 0, 0]

# Memory
vram_gb = [80, 80, 80, 80, 141, 192, 288, 96, 48, 192, 256]
mem_bw_tbps = [2.039, 1.935, 3.350, 2.000, 4.800, 8.000, 8.000, 1.792, 0.864, 5.300, 6.000]

# Power
tdp_w = [400, 300, 700, 350, 700, 1000, 1400, 600, 350, 750, 1000]

# Cost - using lowest on-demand from the matrix (mid-2026)
cost_ondemand = [1.19, 1.19, 2.29, 1.79, 3.19, 4.99, 6.50, 1.50, 0.79, 1.71, 2.50]
cost_cheapest = [1.07, 1.07, 2.01, 1.79, 3.19, 2.12, 6.50, 1.50, 0.79, 1.71, 2.50]

colors = ['#4C72B0', '#4C72B0', '#DD8452', '#DD8452', '#DD8452',
          '#55A868', '#55A868', '#C44E52', '#8172B2', '#937860', '#937860']
hatches = ['', '//', '', '//', '', '', '', '', '', '', '//']

def plot_bar(ax, values, title, ylabel, color_single=None, log=False):
    bars = ax.bar(range(len(gpus)), values, color=colors if color_single is None else [color_single]*len(gpus), edgecolor='black', linewidth=0.8)
    for bar, hatch in zip(bars, hatches):
        bar.set_hatch(hatch)
    ax.set_xticks(range(len(gpus)))
    ax.set_xticklabels(gpu_labels_short, rotation=30, ha='right', fontsize=8)
    ax.set_title(title, fontweight='bold')
    ax.set_ylabel(ylabel)
    ax.grid(axis='y', alpha=0.3)
    if log:
        ax.set_yscale('log')
    for i, v in enumerate(values):
        if v > 0:
            ax.text(i, v * 1.02, f'{v:.1f}' if v < 1000 else f'{v:.0f}', ha='center', va='bottom', fontsize=6, rotation=90)

def plot_barh(ax, values, title, xlabel, color_single=None):
    bars = ax.barh(range(len(gpus)), values, color=colors if color_single is None else [color_single]*len(gpus), edgecolor='black', linewidth=0.8)
    for bar, hatch in zip(bars, hatches):
        bar.set_hatch(hatch)
    ax.set_yticks(range(len(gpus)))
    ax.set_yticklabels(gpu_labels_short, fontsize=8)
    ax.set_title(title, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.grid(axis='x', alpha=0.3)
    for i, v in enumerate(values):
        if v > 0:
            ax.text(v * 1.02, i, f'{v:.2f}' if v < 10 else f'{v:.0f}', va='center', fontsize=7)

# ====== COST METRICS ======
cost_per_vram_gb = [c / v for c, v in zip(cost_ondemand, vram_gb)]

# Performance/Cost ratios (using cheapest price for best-case)
fp16_per_dollar_cheap = [fp16 / c if c > 0 else 0 for fp16, c in zip(fp16_tflops, cost_cheapest)]
fp8_per_dollar_cheap = [fp8 / c if c > 0 else 0 for fp8, c in zip(fp8_tflops, cost_cheapest)]
mem_bw_per_dollar = [bw / c for bw, c in zip(mem_bw_tbps, cost_ondemand)]
vram_per_dollar = [v / c for v, c in zip(vram_gb, cost_ondemand)]

# Efficiency
fp16_per_watt = [fp16 / t if t > 0 else 0 for fp16, t in zip(fp16_tflops, tdp_w)]

fig = plt.figure(figsize=(24, 20))

# 1. VRAM Capacity
ax1 = fig.add_subplot(4, 3, 1)
plot_bar(ax1, vram_gb, 'VRAM Capacity (GB)', 'GB')

# 2. Memory Bandwidth
ax2 = fig.add_subplot(4, 3, 2)
plot_bar(ax2, [b * 1000 for b in mem_bw_tbps], 'Memory Bandwidth (GB/s)', 'GB/s')

# 3. FP16 Tensor TFLOPS (Dense)
ax3 = fig.add_subplot(4, 3, 3)
plot_bar(ax3, fp16_tflops, 'FP16 Tensor TFLOPS (Dense)', 'TFLOPS')

# 4. FP8 Tensor TFLOPS (Dense)
ax4 = fig.add_subplot(4, 3, 4)
plot_bar(ax4, fp8_tflops, 'FP8 Tensor TFLOPS (Dense)', 'TFLOPS')

# 5. On-Demand Cost per Hour
ax5 = fig.add_subplot(4, 3, 5)
plot_bar(ax5, cost_ondemand, 'Cloud On-Demand Cost ($/GPU/hr)', '$/hr')

# 6. Performance per Dollar: FP16 TFLOPS per $/hr (cheapest price)
ax6 = fig.add_subplot(4, 3, 6)
plot_bar(ax6, fp16_per_dollar_cheap, 'FP16 TFLOPS per $/hr (Best Price)', 'FP16 TFLOPS/$/hr')

# 7. Performance per Dollar: FP8 TFLOPS per $/hr (cheapest price)
ax7 = fig.add_subplot(4, 3, 7)
plot_bar(ax7, fp8_per_dollar_cheap, 'FP8 TFLOPS per $/hr (Best Price)', 'FP8 TFLOPS/$/hr')

# 8. Memory Bandwidth per Dollar
ax8 = fig.add_subplot(4, 3, 8)
plot_bar(ax8, mem_bw_per_dollar, 'Memory Bandwidth (TB/s) per $/hr', 'TB/s per $/hr')

# 9. VRAM GB per Dollar
ax9 = fig.add_subplot(4, 3, 9)
plot_bar(ax9, vram_per_dollar, 'VRAM GB per $/hr', 'GB per $/hr')

# 10. Cost per VRAM GB
ax10 = fig.add_subplot(4, 3, 10)
plot_bar(ax10, cost_per_vram_gb, 'Cost per VRAM GB ($/hr/GB)', '$/hr/GB')

# 11. FP16 TFLOPS per Watt (Power Efficiency)
ax11 = fig.add_subplot(4, 3, 11)
plot_bar(ax11, fp16_per_watt, 'FP16 TFLOPS per Watt (Efficiency)', 'FP16 TFLOPS/W')

# 12. TDP
ax12 = fig.add_subplot(4, 3, 12)
plot_bar(ax12, tdp_w, 'Thermal Design Power (W)', 'Watts')

plt.tight_layout(pad=2.0)
plt.savefig('/home/tenbitsolutions/scraper-service/aiminingco_data_v2/gpu_comparison_graphs.png', dpi=200, bbox_inches='tight')
plt.close()
print("Saved: gpu_comparison_graphs.png")

# ====== KEY RATIO CHARTS (Standalone) ======
fig2, axes = plt.subplots(2, 3, figsize=(20, 12))

# Ratio: FP16 TFLOPS per $
ratio_names = ['FP16 TFLOPS\nper $/hr', 'FP8 TFLOPS\nper $/hr', 'Mem BW (TB/s)\nper $/hr',
               'VRAM GB\nper $/hr', 'FP16 TFLOPS\nper Watt', 'Cost per\nVRAM GB ($)']

for idx, (ax, values, title) in enumerate(zip(axes.flat, [
    fp16_per_dollar_cheap, fp8_per_dollar_cheap, mem_bw_per_dollar,
    vram_per_dollar, fp16_per_watt, cost_per_vram_gb
], ratio_names)):
    bars = ax.barh(range(len(gpus)), values, color=colors, edgecolor='black', linewidth=0.8)
    for bar, hatch in zip(bars, hatches):
        bar.set_hatch(hatch)
    ax.set_yticks(range(len(gpus)))
    ax.set_yticklabels(gpu_labels_short, fontsize=7)
    ax.set_title(title, fontweight='bold', fontsize=12)
    ax.grid(axis='x', alpha=0.3)
    for i, v in enumerate(values):
        if v > 0:
            ax.text(v * 1.02, i, f'{v:.2f}', va='center', fontsize=7)

plt.tight_layout(pad=2.0)
plt.savefig('/home/tenbitsolutions/scraper-service/aiminingco_data_v2/gpu_ratios.png', dpi=200, bbox_inches='tight')
plt.close()
print("Saved: gpu_ratios.png")

# ====== TOP PERFORMERS PER METRIC (Horizontal bars, sorted) ======
fig3, axes3 = plt.subplots(2, 2, figsize=(18, 12))

metrics_data = [
    ('FP16 TFLOPS per $/hr (Cheapest)', fp16_per_dollar_cheap, 'FP16 TFLOPS/$'),
    ('FP8 TFLOPS per $/hr (Cheapest)', fp8_per_dollar_cheap, 'FP8 TFLOPS/$'),
    ('VRAM GB per $/hr', vram_per_dollar, 'GB/$'),
    ('Memory Bandwidth per $/hr', mem_bw_per_dollar, 'TB/s per $'),
]

for ax, (title, data, xlabel) in zip(axes3.flat, metrics_data):
    sorted_idx = np.argsort(data)
    sorted_gpus = [gpu_labels_short[i] for i in sorted_idx]
    sorted_vals = [data[i] for i in sorted_idx]
    sorted_colors = [colors[i] for i in sorted_idx]
    
    bars = ax.barh(range(len(sorted_gpus)), sorted_vals, color=sorted_colors, edgecolor='black', linewidth=0.8)
    ax.set_yticks(range(len(sorted_gpus)))
    ax.set_yticklabels(sorted_gpus, fontsize=7)
    ax.set_title(title, fontweight='bold', fontsize=11)
    ax.set_xlabel(xlabel)
    ax.grid(axis='x', alpha=0.3)
    for i, v in enumerate(sorted_vals):
        if v > 0:
            ax.text(v * 1.02, i, f'{v:.2f}', va='center', fontsize=7)

plt.tight_layout(pad=2.0)
plt.savefig('/home/tenbitsolutions/scraper-service/aiminingco_data_v2/gpu_sorted_ratios.png', dpi=200, bbox_inches='tight')
plt.close()
print("Saved: gpu_sorted_ratios.png")

# ====== Grouped comparison: FP16 / FP8 / BW / VRAM normalized to A100 SXM4 ======
fig4, ax4 = plt.subplots(figsize=(20, 8))
x = np.arange(len(gpus))
width = 0.18
multiplier = 0

# Normalize to A100 SXM4 (= 1.0)
a100_fp16 = fp16_tflops[0]
a100_bw = mem_bw_tbps[0]
a100_vram = vram_gb[0]

fp16_norm = [f / a100_fp16 for f in fp16_tflops]
bw_norm = [b / a100_bw for b in mem_bw_tbps]
vram_norm = [v / a100_vram for v in vram_gb]
cost_norm = [cost_ondemand[0] / c if c > 0 else 0 for c in cost_ondemand]  # lower is better, invert

for label, values, color, hatch_pattern in [
    ('FP16 TFLOPS', fp16_norm, '#4C72B0', ''),
    ('Mem Bandwidth', bw_norm, '#55A868', '//'),
    ('VRAM Capacity', vram_norm, '#DD8452', '..'),
    ('Cost Efficiency\n(lower cost = higher)', cost_norm, '#C44E52', 'xx'),
]:
    offset = width * multiplier
    bars = ax4.bar(x + offset, values, width, label=label, color=color, edgecolor='black', linewidth=0.8, alpha=0.85)
    for bar in bars:
        bar.set_hatch(hatch_pattern)
    multiplier += 1

ax4.set_xticks(x + width * 1.5)
ax4.set_xticklabels(gpu_labels_short, rotation=30, ha='right', fontsize=8)
ax4.set_title('Performance & Value Relative to A100 SXM4 (1.0x baseline)', fontweight='bold')
ax4.set_ylabel('Multiplier vs A100 SXM4')
ax4.axhline(y=1.0, color='gray', linestyle='--', linewidth=0.8, alpha=0.5)
ax4.legend(fontsize=10, loc='upper left')
ax4.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('/home/tenbitsolutions/scraper-service/aiminingco_data_v2/gpu_relative_to_a100.png', dpi=200, bbox_inches='tight')
plt.close()
print("Saved: gpu_relative_to_a100.png")

# ====== Scatter: Performance vs Cost ======
fig5, axes5 = plt.subplots(1, 2, figsize=(18, 8))

# FP16 TFLOPS vs Cost
ax = axes5[0]
ax.scatter(cost_ondemand, fp16_tflops, c=colors, s=200, edgecolors='black', linewidth=0.8, zorder=5)
for i, gpu in enumerate(gpu_labels_short):
    ax.annotate(gpu.replace('\n', ' '), (cost_ondemand[i], fp16_tflops[i]),
                textcoords="offset points", xytext=(5, 5), fontsize=8)
ax.set_xlabel('On-Demand Cost ($/hr)')
ax.set_ylabel('FP16 TFLOPS (Dense)')
ax.set_title('FP16 Compute vs Cost (Best quadrant = top-left)', fontweight='bold')
ax.grid(alpha=0.3)

# VRAM vs Cost
ax = axes5[1]
ax.scatter(cost_ondemand, vram_gb, c=colors, s=200, edgecolors='black', linewidth=0.8, zorder=5)
for i, gpu in enumerate(gpu_labels_short):
    ax.annotate(gpu.replace('\n', ' '), (cost_ondemand[i], vram_gb[i]),
                textcoords="offset points", xytext=(5, 5), fontsize=8)
ax.set_xlabel('On-Demand Cost ($/hr)')
ax.set_ylabel('VRAM (GB)')
ax.set_title('VRAM vs Cost (Best quadrant = top-left)', fontweight='bold')
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig('/home/tenbitsolutions/scraper-service/aiminingco_data_v2/gpu_scatter_perf_vs_cost.png', dpi=200, bbox_inches='tight')
plt.close()
print("Saved: gpu_scatter_perf_vs_cost.png")

# ====== Video Generation Specific: Wan 14B Cost per Clip Estimate ======
# Using published benchmarks for generation time
fig6, ax6 = plt.subplots(figsize=(16, 6))

gpu_gen = ['A100\nSXM4', 'H100\nSXM5', 'H200\nSXM', 'B200\nSXM', 'L40S']
gen_time_480p = [170, 85, 70, 50, 500]  # seconds, estimated where not published
gen_cost_480p = [t / 3600 * c for t, c in zip(gen_time_480p, [1.19, 2.29, 3.19, 4.99, 0.79])]
gen_time_720p = [523, 284, 220, 150, None]  # L40S OOM at 720p
gen_cost_720p = [t / 3600 * c if t else 0 for t, c in zip(gen_time_720p, [1.19, 2.29, 3.19, 4.99, 0.79])]

x = np.arange(len(gpu_gen))
width = 0.35

bars1 = ax6.bar(x - width/2, [c * 100 for c in gen_cost_480p], width, label='480p Cost (cents)', color='#4C72B0', edgecolor='black')
bars2 = ax6.bar(x + width/2, [c * 100 if c else 0 for c in gen_cost_720p], width, label='720p Cost (cents)', color='#DD8452', edgecolor='black')

for label, t in zip(gpu_gen, gen_time_720p):
    if t is None:
        ax6.text(list(gpu_gen).index(label), 0, 'OOM', ha='center', fontsize=9, fontweight='bold', color='red')

ax6.set_xticks(x)
ax6.set_xticklabels(gpu_gen, fontsize=9)
ax6.set_title('Estimated Cost per Wan 2.1 14B Clip (5-second generation)', fontweight='bold')
ax6.set_ylabel('Cost per Clip (cents USD)')
ax6.legend()
ax6.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.savefig('/home/tenbitsolutions/scraper-service/aiminingco_data_v2/gpu_video_gen_cost_per_clip.png', dpi=200, bbox_inches='tight')
plt.close()
print("Saved: gpu_video_gen_cost_per_clip.png")

print("\nAll graphs generated successfully!")
print("Files:")
print("  - gpu_comparison_graphs.png (12 subplots: all raw metrics)")
print("  - gpu_ratios.png (6 key ratio charts)")
print("  - gpu_sorted_ratios.png (top ratios sorted)")
print("  - gpu_relative_to_a100.png (normalized comparison)")
print("  - gpu_scatter_perf_vs_cost.png (scatter plots)")
print("  - gpu_video_gen_cost_per_clip.png (video gen cost estimates)")
