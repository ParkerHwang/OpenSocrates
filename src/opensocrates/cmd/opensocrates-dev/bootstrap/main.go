// Bootstrap only seeds exact public trust assets to break the Go embed compiler
// cycle when bringing up a source checkout. Normal generation repeats the copy
// and verifies exact equivalence. It creates no signing key or trust decision.
package main

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
)

func main() {
	root := "."
	if len(os.Args) == 2 {
		root = os.Args[1]
	} else if len(os.Args) != 1 {
		fmt.Fprintln(os.Stderr, "usage: bootstrap [repository-root]")
		os.Exit(2)
	}
	for _, name := range []string{"root.json", "identities.json"} {
		source := filepath.Join(root, "config/update", name)
		info, e := os.Lstat(source)
		if e != nil || !info.Mode().IsRegular() {
			fmt.Fprintln(os.Stderr, "canonical public trust input unavailable")
			os.Exit(1)
		}
		data, e := os.ReadFile(source)
		if e != nil {
			os.Exit(1)
		}
		output := filepath.Join(root, "src/opensocrates/internal/update/trustconfig", name)
		if e = os.MkdirAll(filepath.Dir(output), 0755); e != nil {
			os.Exit(1)
		}
		if e = os.WriteFile(output, data, 0644); e != nil {
			os.Exit(1)
		}
		actual, e := os.ReadFile(output)
		if e != nil || !bytes.Equal(data, actual) {
			fmt.Fprintln(os.Stderr, "public trust asset copy failed")
			os.Exit(1)
		}
	}
	fmt.Println("public trust assets generated")
}
