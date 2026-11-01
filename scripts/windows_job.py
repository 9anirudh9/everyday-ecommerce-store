"""Contain a suspended Windows child before it can spawn descendants (stdlib only)."""
import ctypes
from ctypes import wintypes


class BasicLimits(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                ('flags', wintypes.DWORD), ('min_working_set', ctypes.c_size_t),
                ('max_working_set', ctypes.c_size_t), ('active_processes', wintypes.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [('basic', BasicLimits), ('io', IoCounters), ('process_memory', ctypes.c_size_t),
                ('job_memory', ctypes.c_size_t), ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]


class ThreadEntry(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('usage', wintypes.DWORD), ('thread_id', wintypes.DWORD),
                ('owner_pid', wintypes.DWORD), ('base_priority', wintypes.LONG),
                ('delta_priority', wintypes.LONG), ('flags', wintypes.DWORD)]


def kernel():
    dll = ctypes.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreateJobObjectW': ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
        'SetInformationJobObject': ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
        'AssignProcessToJobObject': ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
        'QueryInformationJobObject': ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
        'CloseHandle': ([wintypes.HANDLE], wintypes.BOOL),
        'CreateToolhelp32Snapshot': ([wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
        'Thread32First': ([wintypes.HANDLE, ctypes.POINTER(ThreadEntry)], wintypes.BOOL),
        'Thread32Next': ([wintypes.HANDLE, ctypes.POINTER(ThreadEntry)], wintypes.BOOL),
        'OpenThread': ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
        'ResumeThread': ([wintypes.HANDLE], wintypes.DWORD),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(dll, name); function.argtypes = arguments; function.restype = result
    return dll


def close_job(handle):
    if not kernel().CloseHandle(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def job_pids(handle):
    class ProcessList(ctypes.Structure):
        _fields_ = [('assigned', wintypes.DWORD), ('listed', wintypes.DWORD), ('pids', ctypes.c_size_t * 4096)]
    data = ProcessList()
    if not kernel().QueryInformationJobObject(handle, 3, ctypes.byref(data), ctypes.sizeof(data), None):
        raise ctypes.WinError(ctypes.get_last_error())
    if data.assigned > 4096 or data.listed > 4096:
        raise RuntimeError('Owned job process list exceeded the bounded limit')
    return set(data.pids[:data.listed])


def contain_and_resume(process):
    dll = kernel(); job = dll.CreateJobObjectW(None, None)
    if not job: raise ctypes.WinError(ctypes.get_last_error())
    snapshot = None
    try:
        limits = ExtendedLimits(); limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not dll.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not dll.AssignProcessToJobObject(job, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        snapshot = dll.CreateToolhelp32Snapshot(0x4, 0)  # TH32CS_SNAPTHREAD
        if snapshot in (None, ctypes.c_void_p(-1).value):
            raise ctypes.WinError(ctypes.get_last_error())
        entry = ThreadEntry(); entry.size = ctypes.sizeof(entry)
        found = dll.Thread32First(snapshot, ctypes.byref(entry))
        while found:
            if entry.owner_pid == process.pid:
                thread = dll.OpenThread(0x0002, False, entry.thread_id)  # THREAD_SUSPEND_RESUME
                if not thread: raise ctypes.WinError(ctypes.get_last_error())
                try:
                    if dll.ResumeThread(thread) != 1:
                        raise RuntimeError('Expected exactly one suspended startup thread')
                finally: dll.CloseHandle(thread)
                return job
            entry.size = ctypes.sizeof(entry)
            found = dll.Thread32Next(snapshot, ctypes.byref(entry))
        raise RuntimeError('Suspended startup thread was not found')
    except Exception:
        process.kill(); process.wait(timeout=10); dll.CloseHandle(job)
        raise
    finally:
        if snapshot not in (None, ctypes.c_void_p(-1).value): dll.CloseHandle(snapshot)
