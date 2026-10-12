//go:build windows

package platform

import (
	"golang.org/x/sys/windows"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
)

// SpawnReplacementHelper is the sole detached execution exception. Only a
// hash-verified Go replacement helper and owner-private request are accepted.
func SpawnReplacementHelper(executable, requestPath, expectedSHA256 string) (int, error) {
	if !strings.EqualFold(filepath.Base(executable), "opensocrates-update-helper.exe") || !digestPattern.MatchString(expectedSHA256) || !hashEquals(executable, expectedSHA256) {
		return 0, failure()
	}
	b, e := ReadFile(requestPath, 64<<10)
	if e != nil {
		return 0, e
	}
	var request ReplacementRequest
	if decodeClosed(b, &request) != nil || request.HelperSHA256 != expectedSHA256 {
		return 0, failure()
	}
	cmd := exec.Command(executable, "--request", requestPath)
	cmd.Env = []string{"SystemRoot=" + systemRoot()}
	cmd.SysProcAttr = &syscall.SysProcAttr{CreationFlags: windows.CREATE_BREAKAWAY_FROM_JOB | windows.DETACHED_PROCESS | windows.CREATE_NEW_PROCESS_GROUP, HideWindow: true}
	if e = cmd.Start(); e != nil {
		return 0, failure()
	}
	pid := cmd.Process.Pid
	if e = cmd.Process.Release(); e != nil {
		return 0, failure()
	}
	return pid, nil
}
func systemRoot() string {
	root, e := SystemExecutable("schtasks.exe")
	if e != nil {
		return ""
	}
	return filepath.Dir(filepath.Dir(root))
}

// SpawnManagerActivationHelper outlives the parent manager's containment job.
// CREATE_BREAKAWAY_FROM_JOB is necessary: a detached console alone still
// inherits a parent's job and would die when the forwarding manager exits.
func SpawnManagerActivationHelper(executable, stateDir string, parentPID int, expectedSHA256 string, parentExecutable ...string) (int, error) {
	if parentPID < 1 || !strings.EqualFold(filepath.Base(executable), "opensocrates-update-helper.exe") || !digestPattern.MatchString(expectedSHA256) || !hashEquals(executable, expectedSHA256) {
		return 0, failure()
	}
	if e := Guard(stateDir); e != nil {
		return 0, e
	}
	info, e := os.Stat(stateDir)
	if e != nil || !info.IsDir() {
		return 0, failure()
	}
	if len(parentExecutable) > 1 {
		return 0, failure()
	}
	args := []string{"--activate-manager", stateDir, "--parent", strconv.Itoa(parentPID)}
	if len(parentExecutable) == 1 && parentExecutable[0] != "" {
		if e = GuardOwned(parentExecutable[0]); e != nil {
			return 0, e
		}
		if info, e = os.Stat(parentExecutable[0]); e != nil || !info.Mode().IsRegular() {
			return 0, failure()
		}
		args = append(args, "--parent-executable", parentExecutable[0])
	}
	cmd := exec.Command(executable, args...)
	cmd.Env = []string{"SystemRoot=" + systemRoot()}
	cmd.SysProcAttr = &syscall.SysProcAttr{CreationFlags: windows.CREATE_BREAKAWAY_FROM_JOB | windows.DETACHED_PROCESS | windows.CREATE_NEW_PROCESS_GROUP, HideWindow: true}
	if e = cmd.Start(); e != nil {
		return 0, failure()
	}
	pid := cmd.Process.Pid
	if e = cmd.Process.Release(); e != nil {
		return 0, failure()
	}
	return pid, nil
}
