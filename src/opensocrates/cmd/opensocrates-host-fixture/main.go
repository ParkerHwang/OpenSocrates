// This executable is a development acceptance fixture, never a release runtime.
package main

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/devtools"
	"os"
)

func main() { os.Exit(devtools.AcceptanceHostFixture(os.Args[1:], os.Stdout)) }
