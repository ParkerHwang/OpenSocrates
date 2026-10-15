// opensocrates-update-helper is the detached Windows activation worker.
package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"runtime"
	"strconv"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/bootstrap"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

func main() {
	if runtime.GOOS != "windows" {
		fmt.Fprintln(os.Stderr, "unsupported: replacement")
		os.Exit(2)
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt)
	defer cancel()
	var err error
	switch {
	case len(os.Args) == 3 && os.Args[1] == "--request":
		err = platform.ReplaceExecutable(ctx, os.Args[2])
	case (len(os.Args) == 5 || len(os.Args) == 7) && os.Args[1] == "--activate-manager" && os.Args[3] == "--parent":
		pid, parseErr := strconv.Atoi(os.Args[4])
		if parseErr != nil || pid < 1 {
			fmt.Fprintln(os.Stderr, "verification: manager-parent")
			os.Exit(2)
		}
		parentExecutable := ""
		if len(os.Args) == 7 {
			if os.Args[5] != "--parent-executable" {
				fmt.Fprintln(os.Stderr, "verification: manager-parent")
				os.Exit(2)
			}
			parentExecutable = os.Args[6]
		}
		err = bootstrap.ActivateManagerForParent(ctx, os.Args[2], pid, parentExecutable)
	default:
		fmt.Fprintln(os.Stderr, "unsupported: replacement")
		os.Exit(2)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println("replacement: verified")
}
