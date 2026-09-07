"""Run a named, repository-reviewed acceptance check locally or in optional CI.

No tracker or PR text is executed. --contract only hashes a snapshot for evidence;
it does not approve that snapshot. The runner is not a sandbox or a coverage proof.
Run from the repo root. Review changes to this runner, registry, and tests together.
"""
import argparse
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import time


CHECK_ID = re.compile(r'[a-z][a-z0-9-]{0,63}')
WORKTREE_SCHEMA = 'ai-first-worktree/v2'


def digest(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def load_check(raw, check_id):
    registry = json.loads(raw, object_pairs_hook=strict_object)
    if not isinstance(registry, dict) or set(registry) != {'schema', 'checks'}:
        raise ValueError('Expected a registry with schema and checks; migrate old argv configs')
    if registry['schema'] != 'ai-first-verification/v1':
        raise ValueError('Unsupported verification registry schema')
    checks = registry['checks']
    if not isinstance(checks, dict) or any(not CHECK_ID.fullmatch(key) for key in checks):
        raise ValueError('Invalid check IDs')
    if not CHECK_ID.fullmatch(check_id) or check_id not in checks:
        raise ValueError(f'Unknown verification check: {check_id}')
    check = checks[check_id]
    if not isinstance(check, dict) or set(check) != {'argv', 'timeout_seconds', 'covers', 'negative_case'}:
        raise ValueError('Each check needs argv, timeout_seconds, covers, and negative_case')
    argv = check['argv']
    if not isinstance(argv, list) or not argv or any(
            not isinstance(arg, str) or not arg.strip() or '\x00' in arg for arg in argv):
        raise ValueError('Configure argv with a real acceptance command before use')
    timeout = check['timeout_seconds']
    if type(timeout) is not int or not 1 <= timeout <= 1500:
        raise ValueError('timeout_seconds must be an integer from 1 to 1500')
    for field in ('covers', 'negative_case'):
        if not isinstance(check[field], str) or not check[field].strip():
            raise ValueError(f'Document {field} before using the check')
    return check


def git(*args):
    return subprocess.run(['git', *args], check=True, capture_output=True).stdout


def file_state(path, object_format, tracked_mode=b'100644'):
    """Return actual mode, SHA-256 content fingerprint, and unfiltered Git blob ID."""
    try:
        info = path.lstat()
    except (FileNotFoundError, NotADirectoryError):
        return b'missing', b'', b''
    content = hashlib.sha256()
    blob = hashlib.new(object_format)
    if stat.S_ISLNK(info.st_mode):
        value = os.fsencode(os.readlink(path))
        blob.update(f'blob {len(value)}\0'.encode())
        blob.update(value)
        content.update(value)
        mode = b'120000'
    elif stat.S_ISREG(info.st_mode):
        blob.update(f'blob {info.st_size}\0'.encode())
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                content.update(chunk)
                blob.update(chunk)
        # Windows has no Unix executable bit. Preserve Git's recorded regular-file
        # mode there; still distinguish real symlinks and hash the actual bytes.
        if os.name == 'nt':
            mode = b'100755' if tracked_mode == b'100755' else b'100644'
        else:
            mode = b'100755' if info.st_mode & stat.S_IXUSR else b'100644'
    elif stat.S_ISDIR(info.st_mode):
        # A tracked file replaced by a directory is different even if all of the
        # directory's new contents are ignored. Non-ignored children are inventoried.
        return b'directory', b'', b''
    else:
        raise ValueError(f'Unsupported special file in verification inputs: {path}')
    return mode, content.digest(), blob.hexdigest().encode()


def worktree_state():
    """Fingerprint raw files and index entries, independently of Git diff settings.

    HEAD paths remain inputs even after a staged deletion. Missing sparse-checkout
    paths are recorded as missing/dirty; submodule contents are not supported.
    """
    head, index = {}, {}
    for record in git('ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
        if record:
            metadata, name = record.split(b'\t', 1)
            mode, kind, oid = metadata.split()
            if kind != b'blob':
                raise ValueError('Cannot fingerprint submodule inputs; use a checkout without submodules')
            head[name] = (mode, oid)
    for record in git('ls-files', '--stage', '-z').split(b'\0'):
        if record:
            metadata, name = record.split(b'\t', 1)
            mode, oid, stage = metadata.split()
            if mode == b'160000':
                raise ValueError('Cannot fingerprint submodule inputs; use a checkout without submodules')
            if stage != b'0':
                raise ValueError('Resolve unmerged index entries before verification')
            index[name] = (mode, oid)
    untracked = set(git('ls-files', '--others', '--exclude-standard', '-z').split(b'\0')) - {b''}
    object_format = git('rev-parse', '--show-object-format').decode().strip()
    state = hashlib.sha256(WORKTREE_SCHEMA.encode() + b'\0')
    dirty = head != index or bool(untracked)
    for name in sorted(set(head) | set(index) | untracked):
        tracked_mode = index.get(name, head.get(name, (b'100644', b'')))[0]
        mode, content, oid = file_state(Path(os.fsdecode(name)), object_format, tracked_mode)
        if name in untracked and mode == b'directory':
            raise ValueError('Cannot fingerprint an untracked nested repository; remove it or explicitly ignore it')
        # Frame every field, including absent index entries and empty file content.
        for part in (name, *index.get(name, (b'absent', b'')), mode, content):
            state.update(len(part).to_bytes(8, 'big'))
            state.update(part)
        dirty = dirty or head.get(name) != (mode, oid)
    return 'sha256:' + state.hexdigest(), dirty


def run_windows_command(argv, timeout):
    """Assign a suspended process to a Job Object before any check code can run.

    Keep this backend in the copied runner so runner_digest binds all execution
    code. Use public Win32 APIs through ctypes; no extra package is required.
    https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
    """
    import ctypes as ct
    from ctypes import wintypes as wt
    import msvcrt

    class BasicLimits(ct.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ct.c_int64), ('PerJobUserTimeLimit', ct.c_int64),
                    ('LimitFlags', wt.DWORD), ('MinimumWorkingSetSize', ct.c_size_t),
                    ('MaximumWorkingSetSize', ct.c_size_t), ('ActiveProcessLimit', wt.DWORD),
                    ('Affinity', ct.c_size_t), ('PriorityClass', wt.DWORD), ('SchedulingClass', wt.DWORD)]

    class IOCounters(ct.Structure):
        _fields_ = [(name, ct.c_uint64) for name in
                    ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                     'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

    class ExtendedLimits(ct.Structure):
        _fields_ = [('BasicLimitInformation', BasicLimits), ('IoInfo', IOCounters),
                    ('ProcessMemoryLimit', ct.c_size_t), ('JobMemoryLimit', ct.c_size_t),
                    ('PeakProcessMemoryUsed', ct.c_size_t), ('PeakJobMemoryUsed', ct.c_size_t)]

    class Accounting(ct.Structure):
        _fields_ = [(name, ct.c_int64) for name in
                    ('TotalUserTime', 'TotalKernelTime', 'ThisPeriodTotalUserTime', 'ThisPeriodTotalKernelTime')]
        _fields_ += [(name, wt.DWORD) for name in
                     ('TotalPageFaultCount', 'TotalProcesses', 'ActiveProcesses', 'TotalTerminatedProcesses')]

    class StartupInfo(ct.Structure):
        _fields_ = [('cb', wt.DWORD), ('lpReserved', wt.LPWSTR), ('lpDesktop', wt.LPWSTR),
                    ('lpTitle', wt.LPWSTR)]
        _fields_ += [(name, wt.DWORD) for name in
                     ('dwX', 'dwY', 'dwXSize', 'dwYSize', 'dwXCountChars', 'dwYCountChars',
                      'dwFillAttribute', 'dwFlags')]
        _fields_ += [('wShowWindow', wt.WORD), ('cbReserved2', wt.WORD), ('lpReserved2', ct.c_void_p),
                     ('hStdInput', wt.HANDLE), ('hStdOutput', wt.HANDLE), ('hStdError', wt.HANDLE)]

    class StartupInfoEx(ct.Structure):
        _fields_ = [('StartupInfo', StartupInfo), ('lpAttributeList', ct.c_void_p)]

    class ProcessInfo(ct.Structure):
        _fields_ = [('hProcess', wt.HANDLE), ('hThread', wt.HANDLE),
                    ('dwProcessId', wt.DWORD), ('dwThreadId', wt.DWORD)]

    kernel = ct.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreateJobObjectW': (wt.HANDLE, [ct.c_void_p, wt.LPCWSTR]),
        'SetInformationJobObject': (wt.BOOL, [wt.HANDLE, ct.c_int, ct.c_void_p, wt.DWORD]),
        'AssignProcessToJobObject': (wt.BOOL, [wt.HANDLE, wt.HANDLE]),
        'TerminateJobObject': (wt.BOOL, [wt.HANDLE, wt.UINT]),
        'QueryInformationJobObject': (wt.BOOL, [wt.HANDLE, ct.c_int, ct.c_void_p, wt.DWORD, ct.c_void_p]),
        'CloseHandle': (wt.BOOL, [wt.HANDLE]),
        'GetCurrentProcess': (wt.HANDLE, []),
        'GetStdHandle': (wt.HANDLE, [wt.DWORD]),
        'DuplicateHandle': (wt.BOOL, [wt.HANDLE, wt.HANDLE, wt.HANDLE, ct.POINTER(wt.HANDLE),
                                    wt.DWORD, wt.BOOL, wt.DWORD]),
        'InitializeProcThreadAttributeList': (wt.BOOL, [ct.c_void_p, wt.DWORD, wt.DWORD, ct.POINTER(ct.c_size_t)]),
        'UpdateProcThreadAttribute': (wt.BOOL, [ct.c_void_p, wt.DWORD, ct.c_size_t, ct.c_void_p,
                                             ct.c_size_t, ct.c_void_p, ct.c_void_p]),
        'DeleteProcThreadAttributeList': (None, [ct.c_void_p]),
        'CreateProcessW': (wt.BOOL, [wt.LPCWSTR, wt.LPWSTR, ct.c_void_p, ct.c_void_p, wt.BOOL,
                                   wt.DWORD, ct.c_void_p, wt.LPCWSTR, ct.POINTER(StartupInfoEx),
                                   ct.POINTER(ProcessInfo)]),
        'ResumeThread': (wt.DWORD, [wt.HANDLE]),
        'WaitForSingleObject': (wt.DWORD, [wt.HANDLE, wt.DWORD]),
        'GetExitCodeProcess': (wt.BOOL, [wt.HANDLE, ct.POINTER(wt.DWORD)]),
        'TerminateProcess': (wt.BOOL, [wt.HANDLE, wt.UINT]),
    }
    for name, (result_type, argument_types) in signatures.items():
        function = getattr(kernel, name)
        function.restype, function.argtypes = result_type, argument_types

    def checked(result):
        if not result:
            raise ct.WinError(ct.get_last_error())
        return result

    with ExitStack() as resources:
        job = checked(kernel.CreateJobObjectW(None, None))
        resources.callback(kernel.CloseHandle, job)
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        checked(kernel.SetInformationJobObject(job, 9, ct.byref(limits), ct.sizeof(limits)))

        # Inherit only standard streams, never the job handle or unrelated handles.
        current = kernel.GetCurrentProcess()
        handles = []
        for std_id, mode in ((-10, 'rb'), (-11, 'wb'), (-12, 'wb')):
            source = kernel.GetStdHandle(std_id)
            if source in (None, ct.c_void_p(-1).value):
                stream = resources.enter_context(open(os.devnull, mode))
                source = msvcrt.get_osfhandle(stream.fileno())
            duplicate = wt.HANDLE()
            checked(kernel.DuplicateHandle(current, source, current, ct.byref(duplicate), 0, True, 2))
            resources.callback(kernel.CloseHandle, duplicate.value)
            handles.append(duplicate.value)
        handle_list = (wt.HANDLE * 3)(*handles)
        size = ct.c_size_t()
        kernel.InitializeProcThreadAttributeList(None, 1, 0, ct.byref(size))
        attributes = ct.create_string_buffer(size.value)
        checked(kernel.InitializeProcThreadAttributeList(attributes, 1, 0, ct.byref(size)))
        resources.callback(kernel.DeleteProcThreadAttributeList, attributes)
        checked(kernel.UpdateProcThreadAttribute(attributes, 0, 0x20002, handle_list,
                                                 ct.sizeof(handle_list), None, None))  # HANDLE_LIST
        startup = StartupInfoEx()
        startup.StartupInfo.cb = ct.sizeof(startup)
        startup.StartupInfo.dwFlags = 0x100  # STARTF_USESTDHANDLES
        startup.StartupInfo.hStdInput, startup.StartupInfo.hStdOutput, startup.StartupInfo.hStdError = handles
        startup.lpAttributeList = ct.cast(attributes, ct.c_void_p)
        process = ProcessInfo()
        command = ct.create_unicode_buffer(subprocess.list2cmdline(argv))
        # CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT prevents the assignment race.
        checked(kernel.CreateProcessW(None, command, None, None, True, 0x4 | 0x80000,
                                      None, None, ct.byref(startup), ct.byref(process)))

        def close_process_handles():
            for field in ('hThread', 'hProcess'):
                handle = getattr(process, field)
                if handle:
                    kernel.CloseHandle(handle)
                    setattr(process, field, None)

        resources.callback(close_process_handles)
        assigned = False
        try:
            checked(kernel.AssignProcessToJobObject(job, process.hProcess))
            assigned = True
            if kernel.ResumeThread(process.hThread) == 0xFFFFFFFF:
                raise ct.WinError(ct.get_last_error())
            deadline = time.monotonic() + timeout
            while True:
                # Short waits let Python handle Ctrl+C while the command runs.
                remaining = max(0, min(100, int((deadline - time.monotonic()) * 1000)))
                status = kernel.WaitForSingleObject(process.hProcess, remaining)
                if status == 0:  # WAIT_OBJECT_0
                    code = wt.DWORD()
                    checked(kernel.GetExitCodeProcess(process.hProcess, ct.byref(code)))
                    return code.value
                if status != 258:  # WAIT_TIMEOUT
                    raise ct.WinError(ct.get_last_error())
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(argv, timeout)
        finally:
            if assigned:
                # Also remove leftover workers after a normal command exit. Wait
                # for termination before the caller fingerprints the final inputs.
                checked(kernel.TerminateJobObject(job, 1))
            elif kernel.WaitForSingleObject(process.hProcess, 0) != 0:
                # Assignment failed: the check is still suspended and must never run.
                checked(kernel.TerminateProcess(process.hProcess, 1))
            if kernel.WaitForSingleObject(process.hProcess, 5000) != 0:
                raise OSError('Windows check process could not be reaped')
            # Release our references before checking the job's active-process count.
            close_process_handles()
            if assigned:
                accounting = Accounting()
                cleanup_deadline = time.monotonic() + 5
                while True:
                    checked(kernel.QueryInformationJobObject(job, 1, ct.byref(accounting),
                                                              ct.sizeof(accounting), None))
                    if not accounting.ActiveProcesses:
                        break
                    if time.monotonic() >= cleanup_deadline:
                        raise OSError('Windows check processes did not terminate within 5 seconds')
                    time.sleep(0.01)


def run_command(argv, timeout):
    """Stop the process tree on timeout or interrupted waiting on either platform."""
    if os.name == 'nt':
        return run_windows_command(argv, timeout)
    with subprocess.Popen(argv, shell=False, start_new_session=True) as process:
        try:
            return process.wait(timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # The group has already exited.
            finally:
                process.wait()
            raise


def run(config_path, check_id='acceptance', contract_path=None):
    try:
        if os.name not in ('posix', 'nt'):
            raise ValueError('The verification runner supports Linux, macOS, and Windows')
        if git('rev-parse', '--show-prefix').strip():
            raise ValueError('Run from the repository root')
        raw = Path(config_path).read_bytes()
        check = load_check(raw, check_id)
        commit = git('rev-parse', 'HEAD').decode().strip()
        before, dirty = worktree_state()
        evidence = dict(schema='ai-first-verification-result/v1', check=check_id,
                        commit=commit, registry_digest=digest(raw),
                        runner_digest=digest(Path(__file__).read_bytes()),
                        contract_digest=None if contract_path is None else digest(Path(contract_path).read_bytes()),
                        dirty=dirty, worktree_schema=WORKTREE_SCHEMA,
                        worktree_digest=before)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'AI-first verification configuration error: {error}', flush=True)
        return 2
    print(f'AI-first verification: check={check_id} commit={commit}', flush=True)
    command_exit = None
    outcome, code = 'error', 2
    try:
        command_exit = run_command(check['argv'], check['timeout_seconds'])
        outcome, code = ('pass', 0) if command_exit == 0 else ('fail', 1)
    except subprocess.TimeoutExpired:
        outcome, code = 'timeout', 124
    except OSError as error:
        print(f'AI-first verification execution error: {error}', flush=True)
    try:
        changed = (git('rev-parse', 'HEAD').decode().strip() != commit
                   or worktree_state()[0] != before
                   or digest(Path(config_path).read_bytes()) != evidence['registry_digest']
                   or digest(Path(__file__).read_bytes()) != evidence['runner_digest']
                   or (contract_path is not None and digest(Path(contract_path).read_bytes()) != evidence['contract_digest']))
        if changed:
            outcome, code = 'inputs-changed', 2
    except (OSError, ValueError, subprocess.SubprocessError):
        outcome, code = 'inputs-unverifiable', 2
    evidence.update(outcome=outcome, command_exit=command_exit)
    print('AI_FIRST_RESULT ' + json.dumps(evidence, sort_keys=True), flush=True)
    return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='.ai-first/ci/verification.json')
    parser.add_argument('--check', default='acceptance')
    parser.add_argument('--contract', help='Optional exact saved task-contract snapshot; hashed, never executed')
    args = parser.parse_args()
    raise SystemExit(run(args.config, args.check, args.contract))
