//go:build !windows

package platform

import (
	"syscall"
)

// ProcessAlive never signals termination or assumes that an inaccessible PID
// is dead. Unknown OS results remain explicit unavailable evidence.
func ProcessAlive(pid int) (bool, error) {
	if pid < 1 {
		return false, failure()
	}
	switch e := syscall.Kill(pid, 0); e {
	case nil, syscall.EPERM:
		return true, nil
	case syscall.ESRCH:
		return false, nil
	default:
		return false, failure()
	}
}
