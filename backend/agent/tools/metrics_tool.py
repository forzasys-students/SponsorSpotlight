from langchain_core.tools import tool


@tool
def rank_brands(file_info: dict, metric: str = "percentage", top_n: int = 3, direction: str = "desc") -> dict:
	"""
	Rank brands by a specified metric from stats.json and return structured JSON.

	Parameters:
	- file_info: includes stats_data.logo_stats
	- metric (enum): one of [percentage, detections, frames, time, coverage_avg_present, coverage_avg_overall, coverage_max, prominence_avg_present, prominence_max, prominence_high_time, share_of_voice_avg_present, share_of_voice_solo_time, share_of_voice_solo_percentage]
	         Synonyms: exposure -> percentage, exposure_percentage -> percentage,
	                   coverage -> coverage_avg_present, present_coverage -> coverage_avg_present,
	                   overall_coverage -> coverage_avg_overall, max_coverage -> coverage_max,
	                   prominence -> prominence_avg_present, prominence_avg -> prominence_avg_present,
	                   max_prominence -> prominence_max,
	                   share_of_voice -> share_of_voice_avg_present, sov -> share_of_voice_avg_present,
	                   solo_time -> share_of_voice_solo_time, solo_percentage -> share_of_voice_solo_percentage
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
	try:
		print(f"[rank_brands] Incoming metric='{metric}' raw='{metric_raw}'")
	except Exception:
		pass
	synonyms = {
		'exposure': 'percentage',
		'exposure_percentage': 'percentage',
		'max_coverage': 'coverage_max',
		'overall_coverage': 'coverage_avg_overall',
		'present_coverage': 'coverage_avg_present',
		'coverage': 'coverage_avg_present',
		'prominence': 'prominence_avg_present',
		'prominence_avg': 'prominence_avg_present',
		'max_prominence': 'prominence_max',
		'share_of_voice': 'share_of_voice_avg_present',
		'sov': 'share_of_voice_avg_present',
		'solo_time': 'share_of_voice_solo_time',
		'solo_percentage': 'share_of_voice_solo_percentage',
		# Explicit space/hyphen variants
		'share of voice': 'share_of_voice_avg_present',
		'average share of voice': 'share_of_voice_avg_present',
		'avg share of voice': 'share_of_voice_avg_present',
		'share-of-voice': 'share_of_voice_avg_present',
	}
	# Also normalize to underscores to tolerate spaces and hyphens
	metric_norm = metric_raw.replace(' ', '_').replace('-', '_')
	metric_name = synonyms.get(metric_raw) or synonyms.get(metric_norm) or metric_norm
	try:
		print(f"[rank_brands] Resolved metric_name='{metric_name}' from raw='{metric_raw}' norm='{metric_norm}'")
	except Exception:
		pass
	allowed = {
		'percentage', 'detections', 'frames', 'time',
		'coverage_avg_present', 'coverage_avg_overall', 'coverage_max',
		'prominence_avg_present', 'prominence_max', 'prominence_high_time',
		'share_of_voice_avg_present', 'share_of_voice_solo_time', 'share_of_voice_solo_percentage'
	}
	if metric_name not in allowed:
		try:
			print(f"[rank_brands] Unsupported metric_name='{metric_name}'. Allowed={sorted(list(allowed))}")
		except Exception:
			pass
		return {
			"metric": metric_name,
			"direction": direction,
			"top_n": max(1, min(int(top_n or 3), 50)),
			"total_brands_considered": 0,
			"items": [],
			"message": "Unsupported metric. Use one of: percentage, detections, frames, time, coverage_avg_present, coverage_avg_overall, coverage_max, prominence_avg_present, prominence_max, prominence_high_time, share_of_voice_avg_present, share_of_voice_solo_time, share_of_voice_solo_percentage."
		}

	rows = []
	for brand, data in logo_stats.items():
		value = data.get(metric_name)
		if isinstance(value, (int, float)):
			rows.append((brand, float(value)))
	try:
		print(f"[rank_brands] Rows considered={len(rows)} for metric='{metric_name}'")
	except Exception:
		pass

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
		if metric_key in {'coverage_avg_present', 'coverage_avg_overall', 'coverage_max'}:
			return f"{val:.2f}%"
		if metric_key in {'share_of_voice_avg_present', 'share_of_voice_solo_percentage'}:
			return f"{val:.2f}%"
		if metric_key == 'share_of_voice_solo_time':
			return f"{val:.2f}s"
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


