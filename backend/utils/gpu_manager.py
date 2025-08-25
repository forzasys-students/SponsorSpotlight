import torch
import subprocess
import threading
import time
import platform

class GPUManager:
    """Handles GPU-related operations like device selection and utilization monitoring."""
    def __init__(self):
        self.device = self._get_device()
        self.device_name = self._get_device_name()
        self.gpu_total_mem_bytes = self._get_gpu_total_mem()
        self._gpu_util_sampler_thread = None
        self._gpu_util_sampling_active = False
        self.gpu_peak_util_pct = None

    def _get_device(self):
        """Determine the best available device for inference."""
        if torch.cuda.is_available():
            return 'cuda'
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return 'mps'
        else:
            return 'cpu'

    def _get_device_name(self):
        """Get the name of the compute device."""
        try:
            if self.device == 'cuda':
                return torch.cuda.get_device_name(0)
            elif self.device == 'mps':
                return 'Apple MPS'
            else:
                return platform.processor() or 'CPU'
        except Exception:
            return 'CPU' if self.device == 'cpu' else 'Unknown GPU'

    def _get_gpu_total_mem(self):
        """Get total GPU memory in bytes if available."""
        if self.device == 'cuda':
            try:
                props = torch.cuda.get_device_properties(0)
                return getattr(props, 'total_memory', None)
            except Exception:
                return None
        return None

    def get_peak_memory_allocated_mb(self):
        """Get peak GPU memory allocated in MB for the current process."""
        if self.device == 'cuda':
            try:
                peak_alloc = torch.cuda.max_memory_allocated()
                return int(peak_alloc / (1024**2)) if peak_alloc else None
            except Exception:
                return None
        return None

    def reset_peak_memory_stats(self):
        """Reset peak GPU memory stats for CUDA device."""
        if self.device == 'cuda':
            try:
                torch.cuda.reset_peak_memory_stats()
            except Exception:
                pass

    def _query_gpu_utilization_pct(self) -> int:
        """Return current GPU utilization percent (0-100) if available, else None."""
        if self.device != 'cuda':
            return None
        # Try NVML first
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            return int(getattr(util, 'gpu', None) or 0)
        except Exception:
            pass
        # Fallback to nvidia-smi
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=1
            )
            if result.returncode == 0:
                line = (result.stdout or '').strip().splitlines()[0]
                return int(line)
        except Exception:
            pass
        return None

    def start_sampling(self):
        """Start sampling GPU utilization in a background thread."""
        if self.device != 'cuda':
            self.gpu_peak_util_pct = None
            return
        self.gpu_peak_util_pct = 0
        self._gpu_util_sampling_active = True
        def _sampler():
            while self._gpu_util_sampling_active:
                try:
                    util = self._query_gpu_utilization_pct()
                    if util is not None:
                        self.gpu_peak_util_pct = max(self.gpu_peak_util_pct or 0, int(util))
                except Exception:
                    pass
                time.sleep(0.5)
        try:
            self._gpu_util_sampler_thread = threading.Thread(target=_sampler, daemon=True)
            self._gpu_util_sampler_thread.start()
        except Exception:
            self._gpu_util_sampling_active = False

    def stop_sampling(self):
        """Stop the GPU utilization sampling thread."""
        try:
            self._gpu_util_sampling_active = False
            t = getattr(self, '_gpu_util_sampler_thread', None)
            if t and t.is_alive():
                t.join(timeout=1.5)
        except Exception:
            pass
