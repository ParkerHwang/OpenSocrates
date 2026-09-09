"""Native Windows owner/DACL checks; no shell or credential access.

Only the current user, SYSTEM and built-in Administrators may receive access.
Unknown/object ACE types and reparse points fail closed. New private objects
receive their owner and protected DACL in the same native create operation;
existing objects are inspected and changed through one stable handle.
"""

from __future__ import annotations

import ctypes
import errno
import msvcrt
import os
import secrets
import sys
from ctypes import wintypes as w
from functools import lru_cache
from pathlib import Path

if sys.platform != "win32":
    raise ImportError("Windows ACL implementation is only available on Windows")


_TOKEN_QUERY = 0x0008
_TOKEN_USER = 1
_TOKEN_OWNER = 4
_OWNER_SECURITY_INFORMATION = 0x00000001
_DACL_SECURITY_INFORMATION = 0x00000004
_PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
_SE_DACL_PROTECTED = 0x1000
_SE_FILE_OBJECT = 1
_READ_CONTROL = 0x00020000
_WRITE_DAC = 0x00040000
_DELETE = 0x00010000
_SYNCHRONIZE = 0x00100000
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_SHARE_DELETE = 0x00000004
_CREATE_NEW = 1
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_DISPOSITION_INFO_CLASS = 4
_FILE_RENAME_INFORMATION_CLASS = 10
_FILE_CREATE = 2
_FILE_DIRECTORY_FILE = 0x00000001
_FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
_FILE_NON_DIRECTORY_FILE = 0x00000040
_OBJ_CASE_INSENSITIVE = 0x00000040
_ERROR_FILE_EXISTS = 80
_ERROR_ALREADY_EXISTS = 183
_SYSTEM_SID = "S-1-5-18"
_ADMINISTRATORS_SID = "S-1-5-32-544"
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# Capability issuance prevents ordinary callers from asserting "newly created"
# with a boolean or public constructor. It is not a sandbox from malicious code
# already executing inside this Python process, which can invoke these OS APIs.


class _SecurityAttributes(ctypes.Structure):
    _fields_ = [
        ("nLength", w.DWORD),
        ("lpSecurityDescriptor", ctypes.c_void_p),
        ("bInheritHandle", w.BOOL),
    ]


class _ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", w.DWORD),
        ("ftCreationTime", w.FILETIME),
        ("ftLastAccessTime", w.FILETIME),
        ("ftLastWriteTime", w.FILETIME),
        ("dwVolumeSerialNumber", w.DWORD),
        ("nFileSizeHigh", w.DWORD),
        ("nFileSizeLow", w.DWORD),
        ("nNumberOfLinks", w.DWORD),
        ("nFileIndexHigh", w.DWORD),
        ("nFileIndexLow", w.DWORD),
    ]


class _FileDispositionInfo(ctypes.Structure):
    _fields_ = [("DeleteFile", ctypes.c_ubyte)]


class _FileRenameInfo(ctypes.Structure):
    _fields_ = [
        ("ReplaceIfExists", ctypes.c_ubyte),
        ("RootDirectory", w.HANDLE),
        ("FileNameLength", w.DWORD),
        ("FileName", w.WCHAR * 1),
    ]


class _UnicodeString(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.c_ushort),
        ("MaximumLength", ctypes.c_ushort),
        ("Buffer", w.LPWSTR),
    ]


class _ObjectAttributes(ctypes.Structure):
    _fields_ = [
        ("Length", w.ULONG),
        ("RootDirectory", w.HANDLE),
        ("ObjectName", ctypes.POINTER(_UnicodeString)),
        ("Attributes", w.ULONG),
        ("SecurityDescriptor", ctypes.c_void_p),
        ("SecurityQualityOfService", ctypes.c_void_p),
    ]


class _IoStatusBlock(ctypes.Structure):
    _fields_ = [("Status", ctypes.c_void_p), ("Information", ctypes.c_size_t)]


class CreatedPrivateTempfile:
    """Factory-issued capability for one handle-relative temporary file."""

    __slots__ = (
        "__active",
        "__descriptor",
        "__file_identity",
        "__issuer",
        "__parent_handle",
        "__parent_path",
        "__path",
    )

    def __init__(
        self,
        *,
        descriptor: int,
        path: str,
        parent_handle: int,
        parent_path: Path,
        file_identity: tuple[int, int, int],
        issuer: object,
    ) -> None:
        if issuer is not _TEMPFILE_CAPABILITY_ISSUER:
            raise TypeError("Windows temporary-file capabilities are factory-issued")
        self.__descriptor = descriptor
        self.__path = path
        self.__parent_handle = parent_handle
        self.__parent_path = parent_path
        self.__file_identity = file_identity
        self.__issuer: object | None = issuer
        self.__active = True

    @property
    def descriptor(self) -> int:
        return self.__descriptor

    @property
    def path(self) -> str:
        return self.__path

    def _issued_and_active(self) -> bool:
        return self.__issuer is _TEMPFILE_CAPABILITY_ISSUER and self.__active

    def _parent(self) -> tuple[int, Path]:
        return self.__parent_handle, self.__parent_path

    def _identity(self) -> tuple[int, int, int]:
        return self.__file_identity

    def _consume(self) -> int | None:
        if not self._issued_and_active():
            return None
        self.__active = False
        self.__issuer = None
        return self.__parent_handle


_TEMPFILE_CAPABILITY_ISSUER = object()


@lru_cache(maxsize=1)
def _api() -> tuple[ctypes.CDLL, ctypes.CDLL, ctypes.CDLL]:
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    pointer = ctypes.c_void_p
    adv.GetSecurityInfo.argtypes = [
        w.HANDLE,
        ctypes.c_int,
        w.DWORD,
        ctypes.POINTER(pointer),
        pointer,
        ctypes.POINTER(pointer),
        pointer,
        ctypes.POINTER(pointer),
    ]
    adv.GetSecurityInfo.restype = w.DWORD
    adv.SetSecurityInfo.argtypes = [
        w.HANDLE,
        ctypes.c_int,
        w.DWORD,
        pointer,
        pointer,
        pointer,
        pointer,
    ]
    adv.SetSecurityInfo.restype = w.DWORD
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
    adv.GetSecurityDescriptorDacl.argtypes = [
        pointer,
        ctypes.POINTER(w.BOOL),
        ctypes.POINTER(pointer),
        ctypes.POINTER(w.BOOL),
    ]
    adv.GetSecurityDescriptorDacl.restype = w.BOOL
    adv.GetSecurityDescriptorControl.argtypes = [
        pointer,
        ctypes.POINTER(ctypes.c_ushort),
        ctypes.POINTER(w.DWORD),
    ]
    adv.GetSecurityDescriptorControl.restype = w.BOOL
    kernel.CreateFileW.argtypes = [
        w.LPCWSTR,
        w.DWORD,
        w.DWORD,
        ctypes.POINTER(_SecurityAttributes),
        w.DWORD,
        w.DWORD,
        w.HANDLE,
    ]
    kernel.CreateFileW.restype = w.HANDLE
    kernel.CreateDirectoryW.argtypes = [w.LPCWSTR, ctypes.POINTER(_SecurityAttributes)]
    kernel.CreateDirectoryW.restype = w.BOOL
    kernel.GetFileInformationByHandle.argtypes = [
        w.HANDLE,
        ctypes.POINTER(_ByHandleFileInformation),
    ]
    kernel.GetFileInformationByHandle.restype = w.BOOL
    kernel.SetFileInformationByHandle.argtypes = [
        w.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        w.DWORD,
    ]
    kernel.SetFileInformationByHandle.restype = w.BOOL
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.LocalFree.argtypes = [pointer]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    ntdll.NtCreateFile.argtypes = [
        ctypes.POINTER(w.HANDLE),
        w.DWORD,
        ctypes.POINTER(_ObjectAttributes),
        ctypes.POINTER(_IoStatusBlock),
        ctypes.c_void_p,
        w.DWORD,
        w.DWORD,
        w.DWORD,
        w.DWORD,
        ctypes.c_void_p,
        w.ULONG,
    ]
    ntdll.NtCreateFile.restype = ctypes.c_long
    ntdll.NtSetInformationFile.argtypes = [
        w.HANDLE,
        ctypes.POINTER(_IoStatusBlock),
        ctypes.c_void_p,
        w.ULONG,
        ctypes.c_int,
    ]
    ntdll.NtSetInformationFile.restype = ctypes.c_long
    ntdll.RtlNtStatusToDosError.argtypes = [ctypes.c_long]
    ntdll.RtlNtStatusToDosError.restype = w.ULONG
    return adv, kernel, ntdll


def _native_path(path: Path) -> str:
    value = str(Path(path).absolute())
    if value.startswith("\\\\?\\"):
        return value
    if value.startswith("\\\\"):
        return "\\\\?\\UNC\\" + value[2:]
    return "\\\\?\\" + value


def _native_nt_path(path: Path) -> str:
    value = _native_path(path)
    if value.startswith("\\\\?\\UNC\\"):
        return "\\??\\UNC\\" + value[8:]
    return "\\??\\" + value[4:]


def _sid_text(sid: int | None) -> str:
    adv, kernel, _ntdll = _api()
    text = w.LPWSTR()
    if not adv.ConvertSidToStringSidW(sid, ctypes.byref(text)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return text.value or ""
    finally:
        kernel.LocalFree(text)


def _token_sid(information_class: int) -> str:
    adv, kernel, _ntdll = _api()
    token = w.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(), _TOKEN_QUERY, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        length = w.DWORD()
        adv.GetTokenInformation(token, information_class, None, 0, ctypes.byref(length))
        buffer = ctypes.create_string_buffer(length.value)
        if not adv.GetTokenInformation(
            token, information_class, buffer, length, ctypes.byref(length)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return _sid_text(ctypes.c_void_p.from_buffer(buffer).value)
    finally:
        kernel.CloseHandle(token)


@lru_cache(maxsize=1)
def current_sid() -> str:
    """Return the process token's user SID, never its configurable default owner."""

    return _token_sid(_TOKEN_USER)


@lru_cache(maxsize=1)
def default_owner_sid() -> str:
    """Return the owner SID Windows applies when creation has no explicit owner."""

    return _token_sid(_TOKEN_OWNER)


def _open_path_handle(path: Path, *, access: int) -> int:
    _adv, kernel, _ntdll = _api()
    handle = kernel.CreateFileW(
        _native_path(path),
        access,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE,
        None,
        _OPEN_EXISTING,
        _FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    if handle == _INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    return int(handle)


def _handle_attributes(handle: int) -> int:
    _adv, kernel, _ntdll = _api()
    information = _ByHandleFileInformation()
    if not kernel.GetFileInformationByHandle(handle, ctypes.byref(information)):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(information.dwFileAttributes)


def _handle_identity(handle: int) -> tuple[int, int, int]:
    _adv, kernel, _ntdll = _api()
    information = _ByHandleFileInformation()
    if not kernel.GetFileInformationByHandle(handle, ctypes.byref(information)):
        raise ctypes.WinError(ctypes.get_last_error())
    return (
        int(information.dwVolumeSerialNumber),
        int(information.nFileIndexHigh),
        int(information.nFileIndexLow),
    )


def _dacl_is_protected(descriptor: ctypes.c_void_p) -> bool:
    adv, _kernel, _ntdll = _api()
    control = ctypes.c_ushort()
    revision = w.DWORD()
    if not adv.GetSecurityDescriptorControl(
        descriptor, ctypes.byref(control), ctypes.byref(revision)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return bool(control.value & _SE_DACL_PROTECTED)


def _inspect_handle(handle: int) -> tuple[bool, bool]:
    """Return owner and private-DACL predicates for one stable object handle."""

    if _handle_attributes(handle) & _FILE_ATTRIBUTE_REPARSE_POINT:
        return False, False
    adv, kernel, _ntdll = _api()
    owner = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    descriptor = ctypes.c_void_p()
    result = adv.GetSecurityInfo(
        handle,
        _SE_FILE_OBJECT,
        _OWNER_SECURITY_INFORMATION | _DACL_SECURITY_INFORMATION,
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
        dacl_protected = _dacl_is_protected(descriptor)
        count = ctypes.c_ushort.from_address(dacl.value + 4).value
        allowed = {user, _SYSTEM_SID, _ADMINISTRATORS_SID}
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
        return owner_ok, user_allow and dacl_protected
    finally:
        kernel.LocalFree(descriptor)


def _path_owner_sid(path: Path) -> str | None:
    """Return the owner SID of a stable non-reparse path handle."""

    adv, kernel, _ntdll = _api()
    handle = _open_path_handle(Path(path), access=_READ_CONTROL)
    try:
        if _handle_attributes(handle) & _FILE_ATTRIBUTE_REPARSE_POINT:
            return None
        owner = ctypes.c_void_p()
        descriptor = ctypes.c_void_p()
        result = adv.GetSecurityInfo(
            handle,
            _SE_FILE_OBJECT,
            _OWNER_SECURITY_INFORMATION,
            ctypes.byref(owner),
            None,
            None,
            None,
            ctypes.byref(descriptor),
        )
        if result:
            raise ctypes.WinError(result)
        try:
            return _sid_text(owner.value)
        finally:
            kernel.LocalFree(descriptor)
    finally:
        kernel.CloseHandle(handle)


def _sid_category(sid: str | None) -> str:
    if sid == current_sid():
        return "current-user"
    if sid == _ADMINISTRATORS_SID:
        return "administrators"
    if sid == _SYSTEM_SID:
        return "system"
    if sid == "S-1-1-0":
        return "everyone"
    return "other"


def _diagnostic_categories(path: Path) -> dict[str, object]:
    """Return only categorical owner/reparse/DACL data suitable for public CI logs."""

    adv, kernel, _ntdll = _api()
    handle = _open_path_handle(Path(path), access=_READ_CONTROL)
    try:
        attributes = _handle_attributes(handle)
        owner = ctypes.c_void_p()
        dacl = ctypes.c_void_p()
        descriptor = ctypes.c_void_p()
        result = adv.GetSecurityInfo(
            handle,
            _SE_FILE_OBJECT,
            _OWNER_SECURITY_INFORMATION | _DACL_SECURITY_INFORMATION,
            ctypes.byref(owner),
            None,
            ctypes.byref(dacl),
            None,
            ctypes.byref(descriptor),
        )
        if result:
            raise ctypes.WinError(result)
        try:
            principal_kinds: set[str] = set()
            if not dacl.value:
                principal_kinds.add("null-dacl")
            else:
                count = ctypes.c_ushort.from_address(dacl.value + 4).value
                for index in range(count):
                    ace = ctypes.c_void_p()
                    if not adv.GetAce(dacl, index, ctypes.byref(ace)) or not ace.value:
                        principal_kinds.add("unreadable-ace")
                        continue
                    kind = ctypes.c_ubyte.from_address(ace.value).value
                    if kind not in {0, 1}:
                        principal_kinds.add("other-ace")
                        continue
                    disposition = "allow" if kind == 0 else "deny"
                    principal_kinds.add(f"{disposition}:{_sid_category(_sid_text(ace.value + 8))}")
            return {
                "owner_kind": _sid_category(_sid_text(owner.value)),
                "reparse": bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT),
                "dacl_protected": _dacl_is_protected(descriptor),
                "dacl_principal_kinds": sorted(principal_kinds),
            }
        finally:
            kernel.LocalFree(descriptor)
    finally:
        kernel.CloseHandle(handle)


def _private_descriptor(*, directory: bool, include_owner: bool) -> ctypes.c_void_p:
    adv, _kernel, _ntdll = _api()
    inherit = "OICI" if directory else ""
    owner = f"O:{current_sid()}" if include_owner else ""
    sddl = (
        owner + "D:P" + "".join(f"(A;{inherit};FA;;;{sid})" for sid in (current_sid(), "SY", "BA"))
    )
    descriptor = ctypes.c_void_p()
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl, 1, ctypes.byref(descriptor), None
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return descriptor


def _descriptor_dacl(descriptor: ctypes.c_void_p) -> ctypes.c_void_p:
    adv, _kernel, _ntdll = _api()
    present = w.BOOL()
    defaulted = w.BOOL()
    dacl = ctypes.c_void_p()
    if not adv.GetSecurityDescriptorDacl(
        descriptor, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    if not present.value or not dacl.value:
        raise PermissionError("Windows private ACL descriptor has no DACL")
    return dacl


def _mark_handle_for_deletion(handle: int) -> None:
    _adv, kernel, _ntdll = _api()
    disposition = _FileDispositionInfo(True)
    if not kernel.SetFileInformationByHandle(
        handle,
        _FILE_DISPOSITION_INFO_CLASS,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def inspect_acl(path: Path) -> tuple[bool, bool]:
    """Return actual owner and owner-only DACL predicates without mutation."""

    if os.name != "nt":
        raise OSError("Windows ACL API requires Windows")
    _adv, kernel, _ntdll = _api()
    handle = _open_path_handle(Path(path), access=_READ_CONTROL)
    try:
        return _inspect_handle(handle)
    finally:
        kernel.CloseHandle(handle)


def secure_acl(path: Path, *, directory: bool) -> None:
    """Protect one current-user-owned, non-reparse object through a stable handle."""

    adv, kernel, _ntdll = _api()
    handle = _open_path_handle(Path(path), access=_READ_CONTROL | _WRITE_DAC)
    try:
        attributes = _handle_attributes(handle)
        if bool(attributes & _FILE_ATTRIBUTE_DIRECTORY) != directory:
            raise PermissionError("Windows ACL target type does not match")
        owner_ok, _private = _inspect_handle(handle)
        if not owner_ok:
            raise PermissionError("Windows ACL target is not owned or is a reparse point")
        descriptor = _private_descriptor(directory=directory, include_owner=False)
        try:
            dacl = _descriptor_dacl(descriptor)
            result = adv.SetSecurityInfo(
                handle,
                _SE_FILE_OBJECT,
                _DACL_SECURITY_INFORMATION | _PROTECTED_DACL_SECURITY_INFORMATION,
                None,
                None,
                dacl,
                None,
            )
            if result:
                raise ctypes.WinError(result)
        finally:
            kernel.LocalFree(descriptor)
        if _inspect_handle(handle) != (True, True):
            raise PermissionError("Windows private ACL verification failed")
    finally:
        kernel.CloseHandle(handle)


def _crt_flags(flags: int) -> int:
    access_mode = flags & (os.O_WRONLY | os.O_RDWR)
    return access_mode | (flags & os.O_APPEND) | getattr(os, "O_BINARY", 0)


def _file_access(flags: int) -> int:
    access_mode = flags & (os.O_WRONLY | os.O_RDWR)
    if access_mode == os.O_WRONLY:
        return _GENERIC_WRITE | _READ_CONTROL
    if access_mode == os.O_RDWR:
        return _GENERIC_READ | _GENERIC_WRITE | _READ_CONTROL
    return _GENERIC_READ | _READ_CONTROL


def create_private_file(path: Path, *, flags: int, share_delete: bool = False) -> int:
    """Create one new private file and return a CRT descriptor for that exact handle."""

    _adv, kernel, _ntdll = _api()
    descriptor = _private_descriptor(directory=False, include_owner=True)
    attributes = _SecurityAttributes(ctypes.sizeof(_SecurityAttributes), descriptor, False)
    try:
        handle = kernel.CreateFileW(
            _native_path(Path(path)),
            _GENERIC_READ | _GENERIC_WRITE | _DELETE,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | (_FILE_SHARE_DELETE if share_delete else 0),
            ctypes.byref(attributes),
            _CREATE_NEW,
            _FILE_ATTRIBUTE_NORMAL,
            None,
        )
        error = ctypes.get_last_error() if handle == _INVALID_HANDLE_VALUE else 0
    finally:
        kernel.LocalFree(descriptor)
    if error:
        if error in {_ERROR_FILE_EXISTS, _ERROR_ALREADY_EXISTS}:
            raise FileExistsError(errno.EEXIST, "private file already exists")
        raise ctypes.WinError(error)
    raw_handle = int(handle)
    try:
        if _inspect_handle(raw_handle) != (True, True):
            raise PermissionError("new Windows file did not receive its private ACL")
        return msvcrt.open_osfhandle(raw_handle, _crt_flags(flags))
    except Exception:
        try:
            _mark_handle_for_deletion(raw_handle)
        finally:
            kernel.CloseHandle(raw_handle)
        raise


def open_private_file(path: Path, *, flags: int, share_delete: bool = False) -> int:
    """Open one existing private file and bind validation to the returned handle."""

    _adv, kernel, _ntdll = _api()
    handle = kernel.CreateFileW(
        _native_path(Path(path)),
        _file_access(flags),
        _FILE_SHARE_READ | _FILE_SHARE_WRITE | (_FILE_SHARE_DELETE if share_delete else 0),
        None,
        _OPEN_EXISTING,
        _FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    if handle == _INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    raw_handle = int(handle)
    try:
        attributes = _handle_attributes(raw_handle)
        if attributes & (_FILE_ATTRIBUTE_DIRECTORY | _FILE_ATTRIBUTE_REPARSE_POINT):
            raise PermissionError("existing Windows file is not a regular file")
        if _inspect_handle(raw_handle) != (True, True):
            raise PermissionError("existing Windows file ACL is unsafe")
        return msvcrt.open_osfhandle(raw_handle, _crt_flags(flags))
    except Exception:
        kernel.CloseHandle(raw_handle)
        raise


def _create_private_file_at(parent_handle: int, filename: str, *, flags: int) -> int:
    """Create one private child relative to an already verified directory handle."""

    if not filename or filename in {".", ".."} or any(char in filename for char in ("/", "\\")):
        raise ValueError("private child must have one filename component")
    _adv, kernel, ntdll = _api()
    descriptor = _private_descriptor(directory=False, include_owner=True)
    native_buffer = ctypes.create_unicode_buffer(filename)
    encoded_length = len(filename.encode("utf-16-le"))
    if encoded_length > 0xFFFC:
        kernel.LocalFree(descriptor)
        raise OSError(errno.ENAMETOOLONG, "private child name is too long")
    unicode_name = _UnicodeString(
        encoded_length,
        encoded_length + 2,
        ctypes.cast(native_buffer, w.LPWSTR),
    )
    attributes = _ObjectAttributes(
        ctypes.sizeof(_ObjectAttributes),
        parent_handle,
        ctypes.pointer(unicode_name),
        _OBJ_CASE_INSENSITIVE,
        descriptor,
        None,
    )
    handle_value = w.HANDLE()
    io_status = _IoStatusBlock()
    try:
        status = int(
            ntdll.NtCreateFile(
                ctypes.byref(handle_value),
                _GENERIC_READ | _GENERIC_WRITE | _READ_CONTROL | _DELETE | _SYNCHRONIZE,
                ctypes.byref(attributes),
                ctypes.byref(io_status),
                None,
                _FILE_ATTRIBUTE_NORMAL,
                _FILE_SHARE_READ | _FILE_SHARE_WRITE,
                _FILE_CREATE,
                _FILE_NON_DIRECTORY_FILE | _FILE_SYNCHRONOUS_IO_NONALERT,
                None,
                0,
            )
        )
    finally:
        kernel.LocalFree(descriptor)
    if status < 0:
        error = int(ntdll.RtlNtStatusToDosError(status))
        if error in {_ERROR_FILE_EXISTS, _ERROR_ALREADY_EXISTS}:
            raise FileExistsError(errno.EEXIST, "private child already exists")
        raise ctypes.WinError(error)
    if handle_value.value is None:
        raise OSError("native private file creation returned no handle")
    handle = int(handle_value.value)
    try:
        attributes_value = _handle_attributes(handle)
        if attributes_value & (_FILE_ATTRIBUTE_DIRECTORY | _FILE_ATTRIBUTE_REPARSE_POINT):
            raise PermissionError("new Windows child is not a regular file")
        if _inspect_handle(handle) != (True, True):
            raise PermissionError("new Windows child did not receive its private ACL")
        return msvcrt.open_osfhandle(handle, _crt_flags(flags))
    except Exception:
        try:
            _mark_handle_for_deletion(handle)
        finally:
            kernel.CloseHandle(handle)
        raise


def _created_tempfile_handle(created: CreatedPrivateTempfile) -> int:
    if type(created) is not CreatedPrivateTempfile or not created._issued_and_active():
        raise PermissionError("Windows temporary-file capability is not active")
    handle = int(msvcrt.get_osfhandle(created.descriptor))
    if _handle_identity(handle) != created._identity():
        raise PermissionError("Windows temporary-file descriptor identity changed")
    attributes = _handle_attributes(handle)
    if attributes & (_FILE_ATTRIBUTE_DIRECTORY | _FILE_ATTRIBUTE_REPARSE_POINT):
        raise PermissionError("Windows temporary-file descriptor is not a regular file")
    return handle


def _validate_created_tempfile(created: CreatedPrivateTempfile) -> tuple[int, int]:
    handle = _created_tempfile_handle(created)
    if _inspect_handle(handle) != (True, True):
        raise PermissionError("Windows temporary-file descriptor ACL is unsafe")
    parent_handle, _parent_path = created._parent()
    parent_attributes = _handle_attributes(parent_handle)
    if not parent_attributes & _FILE_ATTRIBUTE_DIRECTORY or parent_attributes & (
        _FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise PermissionError("Windows temporary-file parent is not a real directory")
    if _inspect_handle(parent_handle) != (True, True):
        raise PermissionError("Windows temporary-file parent ACL is unsafe")
    return handle, parent_handle


def _consume_created_tempfile(created: CreatedPrivateTempfile) -> None:
    parent_handle = created._consume()
    if parent_handle is not None:
        _adv, kernel, _ntdll = _api()
        kernel.CloseHandle(parent_handle)


def create_private_tempfile(*, prefix: str, suffix: str, directory: Path) -> CreatedPrivateTempfile:
    """Create a private child and retain its verified parent handle through publication."""

    root = Path(directory).absolute()
    _adv, kernel, _ntdll = _api()
    parent_handle = _open_path_handle(root, access=_GENERIC_READ | _READ_CONTROL)
    try:
        parent_attributes = _handle_attributes(parent_handle)
        if not parent_attributes & _FILE_ATTRIBUTE_DIRECTORY or parent_attributes & (
            _FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise PermissionError("Windows temporary-file parent is not a real directory")
        if _inspect_handle(parent_handle) != (True, True):
            raise PermissionError("Windows temporary-file parent ACL is unsafe")
        for _attempt in range(100):
            filename = f"{prefix}{secrets.token_hex(8)}{suffix}"
            try:
                descriptor = _create_private_file_at(parent_handle, filename, flags=os.O_RDWR)
            except FileExistsError:
                continue
            try:
                handle = int(msvcrt.get_osfhandle(descriptor))
                return CreatedPrivateTempfile(
                    descriptor=descriptor,
                    path=str(root / filename),
                    parent_handle=parent_handle,
                    parent_path=root,
                    file_identity=_handle_identity(handle),
                    issuer=_TEMPFILE_CAPABILITY_ISSUER,
                )
            except Exception:
                try:
                    discard_created_file_descriptor(descriptor)
                finally:
                    os.close(descriptor)
                raise
        raise FileExistsError(errno.EEXIST, "unable to allocate a unique private file")
    except Exception:
        kernel.CloseHandle(parent_handle)
        raise


def release_created_private_tempfile(created: CreatedPrivateTempfile) -> None:
    """Release a verified create capability when its random filename is the final name."""

    _validate_created_tempfile(created)
    _consume_created_tempfile(created)


def discard_created_private_tempfile(created: CreatedPrivateTempfile) -> None:
    """Delete the exact temporary file and release its retained parent handle."""

    try:
        handle = _created_tempfile_handle(created)
        _mark_handle_for_deletion(handle)
    finally:
        _consume_created_tempfile(created)


def discard_created_file_descriptor(descriptor: int) -> None:
    """Mark the exact new file behind a live descriptor for deletion on close."""

    handle = int(msvcrt.get_osfhandle(descriptor))
    _mark_handle_for_deletion(handle)


def verify_private_file_descriptor(descriptor: int) -> None:
    """Verify one regular private file through its exact live descriptor."""

    handle = int(msvcrt.get_osfhandle(descriptor))
    attributes = _handle_attributes(handle)
    if attributes & (_FILE_ATTRIBUTE_DIRECTORY | _FILE_ATTRIBUTE_REPARSE_POINT):
        raise PermissionError("Windows descriptor is not a regular private file")
    if _inspect_handle(handle) != (True, True):
        raise PermissionError("Windows descriptor ACL is unsafe")


def replace_created_file_descriptor(created: CreatedPrivateTempfile, destination: Path) -> None:
    """Rename one exact child within the same retained, verified parent handle."""

    handle, parent_handle = _validate_created_tempfile(created)
    destination = Path(destination)
    _held_parent, parent_path = created._parent()
    if destination.parent.absolute() != parent_path:
        raise PermissionError("atomic destination changed the verified parent directory")
    filename = destination.name
    if not filename or filename in {".", ".."} or any(char in filename for char in ("/", "\\")):
        raise ValueError("atomic destination must have one filename component")
    name = filename.encode("utf-16-le")
    offset = _FileRenameInfo.FileName.offset
    buffer = ctypes.create_string_buffer(ctypes.sizeof(_FileRenameInfo) + len(name))
    information = ctypes.cast(buffer, ctypes.POINTER(_FileRenameInfo)).contents
    information.ReplaceIfExists = 1
    information.FileNameLength = len(name)
    ctypes.memmove(ctypes.addressof(buffer) + offset, name, len(name))
    _adv, _kernel, _ntdll = _api()
    information.RootDirectory = parent_handle
    io_status = _IoStatusBlock()
    status = int(
        _ntdll.NtSetInformationFile(
            handle,
            ctypes.byref(io_status),
            buffer,
            len(buffer),
            _FILE_RENAME_INFORMATION_CLASS,
        )
    )
    if status < 0:
        raise ctypes.WinError(int(_ntdll.RtlNtStatusToDosError(status)))
    if _handle_identity(handle) != created._identity():
        raise PermissionError("renamed Windows file identity changed")
    _consume_created_tempfile(created)


def create_private_directory(path: Path) -> None:
    """Create one new private directory and validate its returned creation handle."""

    _adv, kernel, ntdll = _api()
    descriptor = _private_descriptor(directory=True, include_owner=True)
    native_name = _native_nt_path(Path(path))
    native_buffer = ctypes.create_unicode_buffer(native_name)
    encoded_length = len(native_name.encode("utf-16-le"))
    if encoded_length > 0xFFFC:
        kernel.LocalFree(descriptor)
        raise OSError(errno.ENAMETOOLONG, "private directory path is too long")
    unicode_name = _UnicodeString(
        encoded_length,
        encoded_length + 2,
        ctypes.cast(native_buffer, w.LPWSTR),
    )
    attributes = _ObjectAttributes(
        ctypes.sizeof(_ObjectAttributes),
        None,
        ctypes.pointer(unicode_name),
        _OBJ_CASE_INSENSITIVE,
        descriptor,
        None,
    )
    handle_value = w.HANDLE()
    io_status = _IoStatusBlock()
    try:
        status = int(
            ntdll.NtCreateFile(
                ctypes.byref(handle_value),
                _GENERIC_READ | _GENERIC_WRITE | _READ_CONTROL | _DELETE,
                ctypes.byref(attributes),
                ctypes.byref(io_status),
                None,
                _FILE_ATTRIBUTE_DIRECTORY,
                _FILE_SHARE_READ | _FILE_SHARE_WRITE,
                _FILE_CREATE,
                _FILE_DIRECTORY_FILE,
                None,
                0,
            )
        )
    finally:
        kernel.LocalFree(descriptor)
    if status < 0:
        error = int(ntdll.RtlNtStatusToDosError(status))
        if error == _ERROR_ALREADY_EXISTS:
            raise FileExistsError(errno.EEXIST, "private directory already exists")
        raise ctypes.WinError(error)

    if handle_value.value is None:
        raise OSError("native private directory creation returned no handle")
    handle = int(handle_value.value)
    try:
        if _inspect_handle(handle) != (True, True):
            raise PermissionError("new Windows directory did not receive its private ACL")
    except Exception:
        _mark_handle_for_deletion(handle)
        raise
    finally:
        kernel.CloseHandle(handle)
