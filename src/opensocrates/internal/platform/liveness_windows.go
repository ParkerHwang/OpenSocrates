//go:build windows

package platform

import (
	"golang.org/x/sys/windows"
)

func ProcessAlive(pid int) (bool, error) {
	if pid < 1 || uint64(pid) > uint64(^uint32(0)) {
		return false, failure()
	}
	h, e := windows.OpenProcess(windows.PROCESS_QUERY_LIMITED_INFORMATION|windows.SYNCHRONIZE, false, uint32(pid))
	if e == windows.ERROR_INVALID_PARAMETER {
		return false, nil
	}
	if e == windows.ERROR_ACCESS_DENIED {
		return true, nil
	}
	if e != nil {
		return false, failure()
	}
	defer windows.CloseHandle(h)
	status, e := windows.WaitForSingleObject(h, 0)
	if e == windows.ERROR_ACCESS_DENIED {
		return true, nil
	}
	if e != nil {
		return false, failure()
	}
	if status == windows.WAIT_OBJECT_0 {
		return false, nil
	}
	if status == uint32(windows.WAIT_TIMEOUT) {
		return true, nil
	}
	return false, failure()
}
