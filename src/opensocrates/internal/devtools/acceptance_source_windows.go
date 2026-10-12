//go:build windows

package devtools

import (
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"golang.org/x/sys/windows"
	"io"
	"os"
)

// Developer-build fixtures may have TOKEN_OWNER=Administrators. This read-only
// source reader is isolated to development acceptance; production package/state
// ownership rules remain strict. Only the new destination gains a user SID.
func readAcceptanceSource(path string, max int64) ([]byte, error) {
	if max < 0 || max > 2<<30 {
		return nil, errors.New("acceptance_source_size_limit")
	}
	lease, e := platform.Lease(path)
	if e != nil {
		return nil, e
	}
	defer lease.Close()
	name, e := windows.UTF16PtrFromString(path)
	if e != nil {
		return nil, errors.New("acceptance_source_invalid")
	}
	handle, e := windows.CreateFile(name, windows.GENERIC_READ, windows.FILE_SHARE_READ|windows.FILE_SHARE_WRITE, nil, windows.OPEN_EXISTING, windows.FILE_FLAG_OPEN_REPARSE_POINT, 0)
	if e != nil {
		return nil, errors.New("acceptance_source_unavailable")
	}
	file := os.NewFile(uintptr(handle), path)
	defer file.Close()
	var before windows.ByHandleFileInformation
	if windows.GetFileInformationByHandle(handle, &before) != nil || before.FileAttributes&(windows.FILE_ATTRIBUTE_REPARSE_POINT|windows.FILE_ATTRIBUTE_DIRECTORY) != 0 || before.NumberOfLinks != 1 {
		return nil, errors.New("linked_or_nonregular_acceptance_source")
	}
	data, e := io.ReadAll(io.LimitReader(file, max+1))
	if e != nil || int64(len(data)) > max {
		return nil, errors.New("acceptance_source_size_limit")
	}
	var after windows.ByHandleFileInformation
	if windows.GetFileInformationByHandle(handle, &after) != nil || before.FileIndexHigh != after.FileIndexHigh || before.FileIndexLow != after.FileIndexLow || before.FileSizeHigh != after.FileSizeHigh || before.FileSizeLow != after.FileSizeLow || before.LastWriteTime != after.LastWriteTime || after.NumberOfLinks != 1 {
		return nil, errors.New("acceptance_source_changed")
	}
	return data, nil
}
