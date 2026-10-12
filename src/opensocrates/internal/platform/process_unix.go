//go:build !windows

package platform

import (
	"io"
	"os/exec"
	"sync"
	"syscall"
)

type group struct {
	pid  int
	once sync.Once
}

func (g *group) Close() error {
	g.once.Do(func() { syscall.Kill(-g.pid, syscall.SIGKILL) })
	return nil
}
func prepareProcess(cmd *exec.Cmd) { cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true} }
func containProcess(cmd *exec.Cmd, trusted bool) (io.Closer, error) {
	return &group{pid: cmd.Process.Pid}, nil
}
