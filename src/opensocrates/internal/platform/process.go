package platform

import (
	"context"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"io"
	"os/exec"
	"sync"
	"time"
)

type RunOptions struct {
	Dir            string
	Env            []string
	Stdin          io.Reader
	Stdout, Stderr io.Writer
	OutputLimit    int64
}
type Result struct {
	Stdout, Stderr []byte
	ExitCode       int
}
type Process struct {
	Cmd         *exec.Cmd
	containment io.Closer
	done        chan struct{}
	once        sync.Once
	waitErr     error
}

func (p *Process) Wait() error { <-p.done; return p.waitErr }
func (p *Process) Close() error {
	p.once.Do(func() {
		if p.containment != nil {
			p.containment.Close()
		}
		if p.Cmd.Process != nil {
			p.Cmd.Process.Kill()
		}
	})
	return nil
}
func Start(ctx context.Context, exe string, args []string, opts RunOptions) (*Process, error) {
	return start(ctx, exe, args, opts, true)
}

// StartTrusted forwards a verified installed first-party executable without
// imposing the external-host 30-second ceiling. Cancellation still owns its tree.
func StartTrusted(ctx context.Context, exe string, args []string, opts RunOptions) (*Process, error) {
	if e := GuardOwned(exe); e != nil {
		return nil, e
	}
	return start(ctx, exe, args, opts, false)
}
func start(ctx context.Context, exe string, args []string, opts RunOptions, bounded bool) (*Process, error) {
	if ctx.Err() != nil {
		return nil, diagnostics.New(diagnostics.HostUnavailable, "process")
	}
	// A bounded default prevents accidental unbounded external host processes.
	cancel := func() {}
	if _, ok := ctx.Deadline(); !ok && bounded {
		ctx, cancel = context.WithTimeout(ctx, 30*time.Second)
	}
	cmd := exec.Command(exe, args...)
	cmd.Dir = opts.Dir
	cmd.Env = opts.Env
	cmd.Stdin = opts.Stdin
	cmd.Stdout = opts.Stdout
	cmd.Stderr = opts.Stderr
	cmd.WaitDelay = time.Second
	prepareProcess(cmd)
	if e := cmd.Start(); e != nil {
		cancel()
		return nil, diagnostics.New(diagnostics.HostUnavailable, "process")
	}
	containment, e := containProcess(cmd, !bounded)
	if e != nil {
		cmd.Process.Kill()
		cmd.Wait()
		cancel()
		return nil, diagnostics.New(diagnostics.Unsupported, "process")
	}
	p := &Process{Cmd: cmd, containment: containment, done: make(chan struct{})}
	go func() {
		defer cancel()
		e := cmd.Wait()
		p.Close()
		if e != nil || ctx.Err() != nil {
			p.waitErr = diagnostics.New(diagnostics.HostUnavailable, "process")
		}
		close(p.done)
	}()
	go func() {
		select {
		case <-ctx.Done():
			p.Close()
		case <-p.done:
		}
	}()
	return p, nil
}

type boundedOutput struct {
	mu       sync.Mutex
	b        []byte
	limit    int64
	overflow context.CancelFunc
}

func (w *boundedOutput) Write(b []byte) (int, error) {
	w.mu.Lock()
	defer w.mu.Unlock()
	if int64(len(w.b))+int64(len(b)) > w.limit {
		if w.overflow != nil {
			w.overflow()
		}
		return 0, diagnostics.New(diagnostics.Verification, "process_output")
	}
	w.b = append(w.b, b...)
	return len(b), nil
}
func Run(ctx context.Context, exe string, args []string, opts RunOptions) (Result, error) {
	limit := opts.OutputLimit
	if limit == 0 {
		limit = 1 << 20
	}
	if limit < 1 || limit > 16<<20 {
		return Result{}, diagnostics.New(diagnostics.Verification, "process_output")
	}
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()
	stdout, stderr := &boundedOutput{limit: limit, overflow: cancel}, &boundedOutput{limit: limit, overflow: cancel}
	if opts.Stdout != nil {
		opts.Stdout = io.MultiWriter(stdout, opts.Stdout)
	} else {
		opts.Stdout = stdout
	}
	if opts.Stderr != nil {
		opts.Stderr = io.MultiWriter(stderr, opts.Stderr)
	} else {
		opts.Stderr = stderr
	}
	p, e := Start(ctx, exe, args, opts)
	if e != nil {
		return Result{}, e
	}
	e = p.Wait()
	return Result{Stdout: stdout.b, Stderr: stderr.b, ExitCode: p.Cmd.ProcessState.ExitCode()}, e
}
