import os
import platform
import ctypes
from dataclasses import dataclass
from typing import Optional
from loguru import logger


@dataclass
class HardwareProfile:
    total_ram_gb: float
    available_ram_gb: float
    cpu_cores_logical: int
    cpu_cores_physical: int
    processor_name: str
    tier: str  # "low_end", "mid_range", "high_end"
    recommended_model_id: str
    recommended_threads: int
    description: str

    def get_description(self, lang_code: Optional[str] = None) -> str:
        from app.i18n.language_manager import tr, LanguageManager
        lang = lang_code or LanguageManager.get_instance().current_language
        if self.tier == "low_end":
            return tr("onboarding.profile_low_desc", ram=self.total_ram_gb)
        elif self.tier == "mid_range":
            return tr("onboarding.profile_mid_desc", ram=self.total_ram_gb)
        else:
            return tr("onboarding.profile_high_desc", ram=self.total_ram_gb)


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def get_windows_ram() -> tuple[float, float]:
    """Returns (total_ram_gb, available_ram_gb) using native Win32 API."""
    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total_gb = stat.ullTotalPhys / (1024 ** 3)
            avail_gb = stat.ullAvailPhys / (1024 ** 3)
            return round(total_gb, 2), round(avail_gb, 2)
    except Exception as e:
        logger.warning(f"Failed to query Win32 memory status: {e}")

    # Fallback to standard approximation
    return 8.0, 4.0


def detect_hardware_specs() -> HardwareProfile:
    """
    Detects CPU and RAM specs and calculates the recommended AI execution profile
    so that Indexo stays fast and consumes minimal resources on weak CPUs.
    """
    total_ram_gb, avail_ram_gb = get_windows_ram()
    logical_cores = os.cpu_count() or 4
    # Estimate physical cores as max(1, logical // 2) if hyperthreaded
    physical_cores = max(1, logical_cores // 2) if logical_cores > 2 else logical_cores
    proc_name = platform.processor() or "CPU x64"

    # Determine recommended profile
    if total_ram_gb < 6.0 or logical_cores <= 2:
        tier = "low_end"
        recommended_model = "qwen2.5-0.5b"
        recommended_threads = max(1, logical_cores - 1)
        desc = f"Perfil Leve (CPU Fraca / {total_ram_gb:.1f} GB RAM detectados): Qwen 2.5 0.5B otimizado para baixo consumo."
    elif total_ram_gb < 14.0:
        tier = "mid_range"
        recommended_model = "qwen2.5-1.5b"
        recommended_threads = min(4, max(2, logical_cores - 1))
        desc = f"Perfil Equilibrado ({total_ram_gb:.1f} GB RAM detectados): Qwen 2.5 1.5B com alto raciocínio e < 2 GB RAM."
    else:
        tier = "high_end"
        recommended_model = "qwen2.5-1.5b"  # 1.5B default, but 3B is available
        recommended_threads = min(6, max(4, logical_cores - 2))
        desc = f"Perfil Alto Desempenho ({total_ram_gb:.1f} GB RAM detectados): Qwen 2.5 1.5B / 3B com máxima precisão."

    return HardwareProfile(
        total_ram_gb=total_ram_gb,
        available_ram_gb=avail_ram_gb,
        cpu_cores_logical=logical_cores,
        cpu_cores_physical=physical_cores,
        processor_name=proc_name,
        tier=tier,
        recommended_model_id=recommended_model,
        recommended_threads=recommended_threads,
        description=desc,
    )
