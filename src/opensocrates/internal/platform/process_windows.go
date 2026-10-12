//go:build windows

package platform

import (
	"golang.org/x/sys/windows"
	"io"
	"os/exec"
	"sync"
	"syscall"
	"unsafe"
)

type job struct {
	handle windows.Handle
	once   sync.Once
}

func (j *job) Close() error {
	j.once.Do(func() { windows.TerminateJobObject(j.handle, 1); windows.CloseHandle(j.handle) })
	return nil
}
func prepareProcess(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{CreationFlags: windows.CREATE_SUSPENDED | windows.CREATE_NEW_PROCESS_GROUP}
}
func containProcess(cmd *exec.Cmd, trusted bool) (io.Closer, error) {
	h, e := windows.CreateJobObject(nil, nil)
	if e != nil {
		return nil, e
	}
	j := &job{handle: h}
	limits := windows.JOBOBJECT_EXTENDED_LIMIT_INFORMATION{}
	limits.BasicLimitInformation.LimitFlags = windows.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
	if trusted {
		limits.BasicLimitInformation.LimitFlags |= windows.JOB_OBJECT_LIMIT_BREAKAWAY_OK
	}
	if _, e = windows.SetInformationJobObject(h, windows.JobObjectExtendedLimitInformation, uintptr(unsafe.Pointer(&limits)), uint32(unsafe.Sizeof(limits))); e != nil {
		j.Close()
		return nil, e
	}
	process, e := windows.OpenProcess(windows.PROCESS_SET_QUOTA|windows.PROCESS_TERMINATE|windows.PROCESS_SUSPEND_RESUME, false, uint32(cmd.Process.Pid))
	if e != nil {
		j.Close()
		return nil, e
	}
	defer windows.CloseHandle(process)
	if e = windows.AssignProcessToJobObject(h, process); e != nil {
		j.Close()
		return nil, e
	}
	// os/exec does not expose its primary thread handle. Resume the suspended
	// process only after it belongs to the kill-on-close job, eliminating the
	// spawn-before-job race where a child could escape cancellation.
	status, _, _ := windows.NewLazySystemDLL("ntdll.dll").NewProc("NtResumeProcess").Call(uintptr(process))
	if status != 0 {
		j.Close()
		return nil, syscall.Errno(status)
	}
	return j, nil
}
