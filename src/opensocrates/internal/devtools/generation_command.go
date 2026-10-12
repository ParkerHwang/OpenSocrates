package devtools

import (
	"flag"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
	"io"
	"os"
	"path/filepath"
	"strings"
)

func runMetadata(command string, args []string) error {
	if command == "metadata-fetch" {
		return update.MetadataFetchCommand(args)
	}
	if command == "metadata-root-rotate" {
		return update.RootRotationCommand(args)
	}
	return update.MetadataCommand(args)
}

// Run is the sole native entrypoint for development and release workflows.
func Run(args []string, out, errout io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(errout, "usage: opensocrates-dev generate|content|schemas|plugins|build|package|sbom|check|acceptance|release-check")
		return 2
	}
	command := args[0]
	args = args[1:]
	if command == "format" {
		if e := RunFormat(".", args); e != nil {
			fmt.Fprintln(errout, e)
			return 1
		}
		fmt.Fprintln(out, "format: OK")
		return 0
	}
	if command == "metadata-sign" || command == "metadata-root-rotate" || command == "metadata-fetch" {
		if e := runMetadata(command, args); e != nil {
			fmt.Fprintln(errout, e)
			return 1
		}
		fmt.Fprintln(out, command+": OK")
		return 0
	}
	if command == "check" {
		return RunChecks(args, out, errout)
	}
	if command == "acceptance" {
		return RunAcceptance(args, out, errout)
	}
	if strings.HasPrefix(command, "release-") && command != "release-check" {
		if e := RunPublication(".", command, args); e != nil {
			fmt.Fprintln(errout, e)
			return 1
		}
		fmt.Fprintln(out, command+": PASS")
		return 0
	}
	f := flag.NewFlagSet(command, flag.ContinueOnError)
	f.SetOutput(errout)
	root := f.String("root", ".", "repository root")
	host := f.String("host", "codex", "distribution profile")
	target := f.String("target", "darwin-arm64", "native target")
	runtimeRoot := f.String("runtime-root", "", "built native runtime root")
	output := f.String("output", "", "output path")
	packagePath := f.String("package", "", "native bundle directory")
	version := f.String("product-version", "", "release version")
	zipOutput := f.String("zip", "", "portable content export")
	if e := f.Parse(args); e != nil {
		return 2
	}
	if len(f.Args()) != 0 {
		fmt.Fprintln(errout, "unexpected arguments")
		return 2
	}
	absolute, e := filepath.Abs(*root)
	if e != nil {
		return 1
	}
	*root = absolute
	if *version == "" {
		b, e := os.ReadFile(filepath.Join(*root, "VERSION"))
		if e != nil {
			fmt.Fprintln(errout, e)
			return 1
		}
		*version = strings.TrimSpace(string(b))
	}
	var result map[string]any
	switch command {
	case "generate":
		e = GenerateTrustConfig(*root)
		if e == nil {
			e = GenerateSchemas(*root)
		}
		if e == nil {
			e = GenerateContent(*root, *version)
		}
		if e == nil {
			for _, h := range []string{"codex", "claude", "claude-chat", "antigravity"} {
				_, e = GeneratePlugin(*root, h, "darwin-arm64", "", "")
				if e != nil {
					break
				}
			}
		}
	case "content":
		e = GenerateContent(*root, *version)
	case "schemas":
		e = GenerateSchemas(*root)
	case "plugins":
		result, e = GeneratePlugin(*root, *host, *target, *runtimeRoot, *output)
		if e == nil && *zipOutput != "" {
			dest := *output
			if dest == "" {
				kind := "plugins"
				if *host == "claude-chat" || *host == "antigravity" {
					kind = "content-hosts"
				}
				dest = filepath.Join(*root, "build/generated", kind, *host)
			}
			e = WritePortableZIP(dest, *zipOutput)
		}
	case "build":
		e = BuildNative(*root, *target, *output)
	case "package":
		result, e = PackageNative(*root, *target, *runtimeRoot, *output)
	case "sbom":
		if *packagePath == "" {
			e = fmt.Errorf("--package required")
		} else {
			if *output == "" {
				*output = filepath.Join(*root, "dist/sbom.json")
			}
			e = WriteSBOM(*packagePath, *output)
		}
	case "release-check":
		if *packagePath == "" {
			e = fmt.Errorf("--package required")
		} else {
			e = CheckNativeRelease(*root, *packagePath, *target, out)
		}
	default:
		fmt.Fprintln(errout, "unknown command", command)
		return 2
	}
	if e != nil {
		fmt.Fprintln(errout, command+": FAIL:", e)
		return 1
	}
	if result != nil && command == "package" {
		fmt.Fprintf(out, "package: OK version=%v target=%v files=%d\n", result["product_version"], result["target"], len(arr(result["files"])))
	} else if result != nil {
		b, e := Canonical(result)
		if e != nil {
			return 1
		}
		_, _ = out.Write(b)
	} else {
		fmt.Fprintln(out, command+": OK")
	}
	return 0
}
