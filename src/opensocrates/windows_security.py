"""Native Windows owner/DACL checks; no shell or credential access.

Only the current user, SYSTEM and built-in Administrators may receive access.
Unknown/object ACE types and reparse points fail closed.
"""

from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes as w
from functools import lru_cache
from pathlib import Path

if sys.platform != "win32":
    raise ImportError("Windows ACL implementation is only available on Windows")


@lru_cache(maxsize=1)
def _api() -> tuple[ctypes.CDLL, ctypes.CDLL]:
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.c_void_p
    adv.GetNamedSecurityInfoW.argtypes = [
        w.LPWSTR,
        w.DWORD,
        w.DWORD,
        ctypes.POINTER(pointer),
        pointer,
        ctypes.POINTER(pointer),
        pointer,
        ctypes.POINTER(pointer),
    ]
    adv.GetNamedSecurityInfoW.restype = w.DWORD
    adv.ConvertSidToStringSidW.argtypes = [pointer, ctypes.POINTER(w.LPWSTR)]
    adv.ConvertSidToStringSidW.restype = w.BOOL
    adv.GetAce.argtypes = [pointer, w.DWORD, ctypes.POINTER(pointer)]
    adv.GetAce.restype = w.BOOL
    adv.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    adv.GetTokenInformation.argtypes = [
        w.HANDLE,
        ctypes.c_int,
        pointer,
        w.DWORD,
        ctypes.POINTER(w.DWORD),
    ]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        w.LPCWSTR,
        w.DWORD,
        ctypes.POINTER(pointer),
        pointer,
    ]
    adv.SetFileSecurityW.argtypes = [w.LPCWSTR, w.DWORD, pointer]
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.LocalFree.argtypes = [pointer]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    return adv, kernel


def _sid_text(sid: int | None) -> str:
    adv, kernel = _api()
    text = w.LPWSTR()
    if not adv.ConvertSidToStringSidW(sid, ctypes.byref(text)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return text.value or ""
    finally:
        kernel.LocalFree(text)


@lru_cache(maxsize=1)
def current_sid() -> str:
    adv, kernel = _api()
    token = w.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        length = w.DWORD()
        adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(length))
        buffer = ctypes.create_string_buffer(length.value)
        if not adv.GetTokenInformation(token, 1, buffer, length, ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        return _sid_text(ctypes.c_void_p.from_buffer(buffer).value)
    finally:
        kernel.CloseHandle(token)


def inspect_acl(path: Path) -> tuple[bool, bool]:
    """Return actual owner and owner-only DACL predicates without mutation."""
    if os.name != "nt":
        raise OSError("Windows ACL API requires Windows")
    if path.lstat().st_file_attributes & 0x400:
        return False, False
    adv, kernel = _api()
    owner = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    descriptor = ctypes.c_void_p()
    result = adv.GetNamedSecurityInfoW(
        str(path),
        1,
        5,
        ctypes.byref(owner),
        None,
        ctypes.byref(dacl),
        None,
        ctypes.byref(descriptor),
    )
    if result:
        raise ctypes.WinError(result)
    try:
        user = current_sid()
        owner_ok = _sid_text(owner.value) == user
        if not dacl.value:
            return owner_ok, False  # NULL DACL permits everyone.
        count = ctypes.c_ushort.from_address(dacl.value + 4).value
        allowed = {user, "S-1-5-18", "S-1-5-32-544"}
        user_allow = False
        for index in range(count):
            ace = ctypes.c_void_p()
            if not adv.GetAce(dacl, index, ctypes.byref(ace)) or not ace.value:
                return owner_ok, False
            kind = ctypes.c_ubyte.from_address(ace.value).value
            if kind == 1:  # Deny ACEs cannot broaden access.
                continue
            if kind != 0:
                return owner_ok, False
            sid = _sid_text(ace.value + 8)
            if sid not in allowed:
                return owner_ok, False
            user_allow |= sid == user
        return owner_ok, user_allow
    finally:
        kernel.LocalFree(descriptor)


def secure_acl(path: Path, *, directory: bool) -> None:
    """Protect an owned path's DACL, preserving SYSTEM/admin recovery access."""
    owner, _ = inspect_acl(path)
    if not owner:
        raise PermissionError("Windows ACL target is not owned or is a reparse point")
    adv, kernel = _api()
    inherit = "OICI" if directory else ""
    sddl = "D:P" + "".join(f"(A;{inherit};FA;;;{sid})" for sid in (current_sid(), "SY", "BA"))
    descriptor = ctypes.c_void_p()
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl, 1, ctypes.byref(descriptor), None
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        if not adv.SetFileSecurityW(str(path), 0x80000004, descriptor):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.LocalFree(descriptor)
    if inspect_acl(path) != (True, True):
        raise PermissionError("Windows private ACL verification failed")
