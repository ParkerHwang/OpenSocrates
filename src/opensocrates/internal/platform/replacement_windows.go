//go:build windows

package platform

import (
	"context"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"golang.org/x/sys/windows"
	"strings"
	"time"
)

func waitOwnedProcess(ctx context.Context, pid int, target string) error {
	if pid == 0 {
		return nil
	}
	h, e := windows.OpenProcess(windows.PROCESS_QUERY_LIMITED_INFORMATION|windows.SYNCHRONIZE, false, uint32(pid))
	if e == windows.ERROR_INVALID_PARAMETER {
		return nil
	}
	if e != nil {
		return failure()
	}
	defer windows.CloseHandle(h)
	var token windows.Token
	if windows.OpenProcessToken(h, windows.TOKEN_QUERY, &token) != nil {
		return failure()
	}
	owner, e := token.GetTokenUser()
	token.Close()
	current, e2 := currentSID()
	if e != nil || e2 != nil || owner == nil || !owner.User.Sid.Equals(current) {
		return failure()
	}
	b := make([]uint16, 32768)
	size := uint32(len(b))
	if windows.QueryFullProcessImageName(h, 0, &b[0], &size) != nil || !strings.EqualFold(windows.UTF16ToString(b[:size]), target) {
		return failure()
	}
	for {
		status, e := windows.WaitForSingleObject(h, 50)
		if e != nil {
			return failure()
		}
		if status == windows.WAIT_OBJECT_0 {
			return nil
		}
		select {
		case <-ctx.Done():
			return diagnostics.New(diagnostics.Locked, "replacement_wait")
		default:
			time.Sleep(time.Millisecond)
		}
	}
}
