package main

import (
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/devtools"
	"os"
)

func main() { os.Exit(devtools.Run(os.Args[1:], os.Stdout, os.Stderr)) }
