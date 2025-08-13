from langchain_core.tools import tool


@tool
def rank_brands(file_info: dict, metric: str = "percentage", top_n: int = 3, direction: str = "desc") -> dict:
	"""
	Rank brands by a specified metric from stats.json and return structured JSON.

	Parameters:
	- file_info: includes stats_data.logo_stats
	- metric (enum): one of [percentage, detections, frames, time, coverage_avg_present, coverage_avg_overall, coverage_max]
	         Synonyms: exposure -> percentage, exposure_percentage -> percentage,
	                   coverage -> coverage_avg_present, present_coverage -> coverage_avg_present,
	                   overall_coverage -> coverage_avg_overall, max_coverage -> coverage_max
	- top_n: integer (1..50), default 3
	- direction: 'desc' or 'asc', default 'desc'

	Returns:
	{
	  "metric": str,
	  "direction": "desc"|"asc",
	  "top_n": int,
	  "total_brands_considered": int,
	  "items": [ {"brand": str, "value": float, "formatted_value": str} ]
	}
	"""
	stats = file_info.get('stats_data') or {}
	logo_stats = stats.get('logo_stats') or {}
	if not logo_stats:
		return {
			"metric": metric,
			"direction": direction,
			"top_n": max(1, min(int(top_n or 3), 50)),
			"total_brands_considered": 0,
			"items": [],
			"message": "No logo statistics available."
		}

	# Normalize metric name
	metric_raw = (metric or 'percentage').strip().lower()
	synonyms = {
		'exposure': 'percentage',
		'exposure_percentage': 'percentage',
		'max_coverage': 'coverage_max',
		'overall_coverage': 'coverage_avg_overall',
		'present_coverage': 'coverage_avg_present',
		'coverage': 'coverage_avg_present',
	}
	metric_name = synonyms.get(metric_raw, metric_raw)
	allowed = {
		'percentage', 'detections', 'frames', 'time',
		'coverage_avg_present', 'coverage_avg_overall', 'coverage_max'
	}
	if metric_name not in allowed:
		return {
			"metric": metric_name,
			"direction": direction,
			"top_n": max(1, min(int(top_n or 3), 50)),
			"total_brands_considered": 0,
			"items": [],
			"message": "Unsupported metric. Use one of: percentage, detections, frames, time, coverage_avg_present, coverage_avg_overall, coverage_max."
		}

	rows = []
	for brand, data in logo_stats.items():
		value = data.get(metric_name)
		if isinstance(value, (int, float)):
			rows.append((brand, float(value)))

	if not rows:
		return {
			"metric": metric_name,
			"direction": direction,
			"top_n": max(1, min(int(top_n or 3), 50)),
			"total_brands_considered": 0,
			"items": [],
			"message": f"No numeric values found for metric '{metric_name}'."
		}

	# Stabilize direction and selection bounds
	dir_lower = str(direction or 'desc').lower()
	reverse = (dir_lower != 'asc')
	# Stable secondary key: brand name ascending for deterministic ties
	rows.sort(key=lambda x: (x[1], x[0]), reverse=reverse)
	limit = max(1, min(int(top_n or 3), 50))
	selected = rows[: limit]

	def fmt(metric_key: str, val: float) -> str:
		if metric_key == 'percentage':
			return f"{val:.2f}%"
		return f"{val:.2f}"

	items = [
		{"brand": brand, "value": val, "formatted_value": fmt(metric_name, val)}
		for brand, val in selected
	]
	return {
		"metric": metric_name,
		"direction": 'desc' if reverse else 'asc',
		"top_n": limit,
		"total_brands_considered": len(rows),
		"items": items,
	}


