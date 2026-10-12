package devtools

import (
	"archive/zip"
	"bytes"
	"context"
	"debug/buildinfo"
	"debug/pe"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strings"
	"time"
)

// BuildNative uses only the pinned Go toolchain. User distribution embeds all
// runtime data and never invokes that toolchain on an installed machine.
func BuildNative(root, target, output string) error {
	goos, arch, suffix, err := nativeBuildTarget(target)
	if err != nil {
		return err
	}
	if output == "" {
		output = filepath.Join(root, "dist/runtime")
	}
	if !filepath.IsAbs(output) {
		output = filepath.Join(root, output)
	}
	destination := filepath.Join(output, target)
	if e := os.MkdirAll(destination, 0755); e != nil {
		return e
	}
	for _, name := range []string{"opensocrates", "opensocrates-update-helper"} {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
		cmd := exec.CommandContext(ctx, "go", "build", "-trimpath", "-buildvcs=true", "-ldflags=-s -w", "-o", filepath.Join(destination, name+suffix), "./src/opensocrates/cmd/"+name)
		cmd.Dir = root
		cmd.Env = append(os.Environ(), "GOOS="+goos, "GOARCH="+arch, "CGO_ENABLED=0")
		b, e := cmd.CombinedOutput()
		cancel()
		if e != nil {
			return fmt.Errorf("native build %s failed: %s", name, string(b))
		}
	}
	return nil
}

func PackageNative(root, target, runtimeRoot, output string) (map[string]any, error) {
	if _, _, _, err := nativeBuildTarget(target); err != nil {
		return nil, err
	}
	if runtimeRoot == "" {
		runtimeRoot = filepath.Join(root, "dist/runtime")
	}
	if !filepath.IsAbs(runtimeRoot) {
		runtimeRoot = filepath.Join(root, runtimeRoot)
	}
	if output == "" {
		output = filepath.Join(root, "dist/native", target)
	}
	if !filepath.IsAbs(output) {
		output = filepath.Join(root, output)
	}
	parent, e := os.MkdirTemp("", "opensocrates-release-")
	if e != nil {
		return nil, e
	}
	defer os.RemoveAll(parent)
	files := map[string][]byte{}
	modes := map[string]os.FileMode{}
	hosts := []string{"codex", "antigravity", "claude-chat"}
	if target == "darwin-arm64" {
		hosts = append(hosts, "claude")
	}
	for _, host := range hosts {
		stage := filepath.Join(parent, host)
		if _, e = GeneratePlugin(root, host, target, runtimeRoot, stage); e != nil {
			return nil, e
		}
		if e = copyPackageTree(parent, host, "packages/"+host, files); e != nil {
			return nil, e
		}
		if host == "claude-chat" || host == "antigravity" {
			versionData, e := os.ReadFile(filepath.Join(root, "VERSION"))
			if e != nil {
				return nil, e
			}
			path := filepath.Join(root, "dist", fmt.Sprintf("opensocrates-%s-v%s.zip", host, strings.TrimSpace(string(versionData))))
			if e = WritePortableZIP(stage, path); e != nil {
				return nil, e
			}
		}
	}
	suffix := ""
	if windowsNativeTarget(target) {
		suffix = ".exe"
	}
	for _, name := range []string{"opensocrates", "opensocrates-update-helper"} {
		b, e := regularRead(runtimeRoot, target+"/"+name+suffix)
		if e != nil {
			return nil, e
		}
		if e = verifyGoBinary(filepath.Join(runtimeRoot, target, name+suffix), target); e != nil {
			return nil, e
		}
		files["bin/"+name+suffix] = b
		modes["bin/"+name+suffix] = 0755
	}
	for path := range files {
		if strings.Contains(path, "/runtime/"+target+"/opensocrates") {
			modes[path] = 0755
		}
	}
	for _, name := range []string{"LICENSE", "THIRD_PARTY_NOTICES.md"} {
		b, e := regularRead(root, name)
		if e == nil {
			files[name] = b
		} else if name == "LICENSE" {
			return nil, e
		}
	}
	bundle, e := ReadObject(filepath.Join(root, "content/compiled-content.bundle.json"))
	if e != nil {
		return nil, e
	}
	commit, e := gitOutput(root, "rev-parse", "HEAD")
	if e != nil {
		return nil, e
	}
	dirty, e := gitOutput(root, "status", "--porcelain")
	if e != nil {
		return nil, e
	}
	manifest := map[string]any{"schema": "opensocrates.native-bundle/1.0.0", "target": target, "product_version": bundle["product_version"], "content_revision": bundle["content_revision"], "source_tree_hash": bundle["source_tree_hash"], "normalized_semantic_hash": bundle["normalized_semantic_hash"], "source_git_commit": strings.TrimSpace(commit), "dirty_tree": strings.TrimSpace(dirty) != "", "runtime_language": "go", "minimum_manager_version": "1.6.0", "state_schema_version": 1, "go_toolchain": runtime.Version(), "files": fileInventory(files, modes)}
	data, e := Canonical(manifest)
	if e != nil {
		return nil, e
	}
	files["bundle-manifest.json"] = data
	if e = commitPackage(root, output, "bundle-manifest.json", files, modes); e != nil {
		return nil, e
	}
	archive := filepath.Join(root, "dist", fmt.Sprintf("opensocrates-v%s-%s.zip", str(bundle["product_version"]), target))
	if e = WritePortableZIP(output, archive); e != nil {
		return nil, e
	}
	standalone := filepath.Join(root, "dist", fmt.Sprintf("opensocrates-v%s-%s%s", str(bundle["product_version"]), target, suffix))
	if e = writeData(standalone, files["bin/opensocrates"+suffix], 0755); e != nil {
		return nil, e
	}
	return manifest, nil
}
func gitOutput(root string, args ...string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, "git", args...)
	cmd.Dir = root
	b, e := cmd.Output()
	return string(b), e
}

func verifyGoBinary(path, target string) error {
	info, e := buildinfo.ReadFile(path)
	if e != nil {
		return fmt.Errorf("native runtime must be a Go executable")
	}
	wantOS, wantArch, _, err := nativeBuildTarget(target)
	if err != nil {
		return err
	}
	settings := map[string]string{}
	for _, setting := range info.Settings {
		settings[setting.Key] = setting.Value
	}
	if settings["GOOS"] != wantOS || settings["GOARCH"] != wantArch || settings["CGO_ENABLED"] != "0" {
		return fmt.Errorf("native runtime target or static build mismatch")
	}
	if windowsNativeTarget(target) {
		return verifyNativePE(path, target)
	}
	return nil
}

func verifyNativePE(path, target string) error {
	binary, err := pe.Open(path)
	if err != nil {
		return fmt.Errorf("native Windows PE header invalid")
	}
	defer binary.Close()
	want := uint16(pe.IMAGE_FILE_MACHINE_AMD64)
	if target == "windows-arm64" {
		want = pe.IMAGE_FILE_MACHINE_ARM64
	} else if target != "windows-x64" {
		return fmt.Errorf("unsupported Windows PE target")
	}
	if binary.FileHeader.Machine != want {
		return fmt.Errorf("native Windows PE machine mismatch")
	}
	if _, ok := binary.OptionalHeader.(*pe.OptionalHeader64); !ok {
		return fmt.Errorf("native Windows PE64 header required")
	}
	return nil
}

func requireNativeExecution(target, goos, arch string) error {
	wantOS, wantArch, _, err := nativeBuildTarget(target)
	if err != nil {
		return err
	}
	if goos != wantOS || arch != wantArch {
		return fmt.Errorf("native target execution required")
	}
	return nil
}

func verifyHelperSignature(path, target string) error {
	if target == "darwin-arm64" {
		if e := verifyMacReleaseSignature(path); e != nil {
			return fmt.Errorf("production helper signature required")
		}
	} else {
		if e := exec.Command("signtool.exe", "verify", "/pa", "/all", "/tw", path).Run(); e != nil {
			return fmt.Errorf("production helper Authenticode required")
		}
	}
	return nil
}

func verifyMacReleaseSignature(path string) error {
	if !filepath.IsAbs(path) {
		// The documented release package path is relative to the checkout.
		// Resolve it without relaxing the platform's lexical-alias policy.
		clean := filepath.Clean(path)
		if path == "" || strings.ContainsRune(path, 0) || (clean != path && clean+string(os.PathSeparator) != path) {
			return diagnostics.New(diagnostics.Permission, "filesystem")
		}
		for _, component := range strings.Split(clean, string(os.PathSeparator)) {
			if component == "." || component == ".." {
				return diagnostics.New(diagnostics.Permission, "filesystem")
			}
		}
		absolute, e := filepath.Abs(path)
		if e != nil {
			return diagnostics.New(diagnostics.Permission, "filesystem")
		}
		path = absolute
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	return platform.VerifyNativeSignature(ctx, path, update.DefaultNativeTrust())
}

func verifyManagerSignature(path, target string) error {
	if target == "darwin-arm64" {
		if e := verifyMacReleaseSignature(path); e != nil {
			return fmt.Errorf("production platform signature required")
		}
	} else {
		if e := exec.Command("signtool.exe", "verify", "/pa", "/all", "/tw", path).Run(); e != nil {
			return fmt.Errorf("production Authenticode signature required")
		}
	}
	return nil
}

type nativeReleaseCommands struct {
	verifyManager func(string, string) error
	verifyHelper  func(string, string) error
	version       func(string) ([]byte, error)
}

// Keep both executable trust gates ahead of executing any candidate code.
// Production callers supply only the fixed OS verifiers and version command;
// the explicit command dependencies allow failure-order tests without signing
// credentials or running an untrusted candidate.
func checkNativeReleaseExecutables(manager, helper, target, version string, commands nativeReleaseCommands) error {
	if e := commands.verifyManager(manager, target); e != nil {
		return e
	}
	if e := commands.verifyHelper(helper, target); e != nil {
		return e
	}
	b, e := commands.version(manager)
	if e != nil || !strings.Contains(string(b), version) {
		return fmt.Errorf("native version execution failed")
	}
	return nil
}

// portableArchiveModes uses generated inventory modes, never host permission
// bits. Windows regular-file metadata cannot represent portable Unix modes.
func portableArchiveModes(source string) (map[string]os.FileMode, map[string]map[string]any, error) {
	rootInfo, err := os.Lstat(source)
	if err != nil || !rootInfo.IsDir() || rootInfo.Mode()&os.ModeSymlink != 0 {
		return nil, nil, fmt.Errorf("archive root must be a regular directory")
	}
	manifestPath := ""
	for _, candidate := range []string{"bundle-manifest.json", "release-manifest.json", "opensocrates/release-manifest.json"} {
		if _, err = os.Lstat(filepath.Join(source, filepath.FromSlash(candidate))); err == nil {
			manifestPath = candidate
			break
		} else if !os.IsNotExist(err) {
			return nil, nil, err
		}
	}
	if manifestPath == "" {
		return nil, nil, fmt.Errorf("generated archive manifest required")
	}
	manifestBytes, err := regularRead(source, manifestPath)
	if err != nil {
		return nil, nil, err
	}
	manifest, err := ReadObject(filepath.Join(source, filepath.FromSlash(manifestPath)))
	if err != nil {
		return nil, nil, err
	}
	canonical, err := Canonical(manifest)
	if err != nil || !bytes.Equal(manifestBytes, canonical) {
		return nil, nil, fmt.Errorf("noncanonical archive manifest")
	}
	contentOnly := manifest["schema"] == schema("content-host-manifest")
	if !contentOnly && manifest["schema"] != schema("plugin-release-manifest") && manifest["schema"] != "opensocrates.native-bundle/1.0.0" {
		return nil, nil, fmt.Errorf("unknown archive manifest schema")
	}
	modes := map[string]os.FileMode{manifestPath: 0644}
	records := map[string]map[string]any{}
	if len(arr(manifest["files"])) == 0 {
		return nil, nil, fmt.Errorf("empty archive inventory")
	}
	for _, raw := range arr(manifest["files"]) {
		record := obj(raw)
		name := str(record["path"])
		if !safeRelative(name) || modes[name] != 0 {
			return nil, nil, fmt.Errorf("unsafe or duplicate archive inventory member")
		}
		var mode os.FileMode
		switch jsonToken(record["mode"]) {
		case "420":
			mode = 0644
		case "493":
			mode = 0755
		default:
			return nil, nil, fmt.Errorf("archive inventory mode must be 0644 or 0755")
		}
		if contentOnly && mode != 0644 {
			return nil, nil, fmt.Errorf("executable content archive member")
		}
		modes[name] = mode
		records[name] = record
	}
	return modes, records, nil
}

// WritePortableZIP emits inventoried regular entries with fixed portable modes
// and timestamp. Hashes, sizes and exact membership are checked before writing;
// host permission bits never determine an archive member's declared mode.
func WritePortableZIP(source, destination string) error {
	modes, records, e := portableArchiveModes(source)
	if e != nil {
		return e
	}
	var paths []string
	e = filepath.WalkDir(source, func(path string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.Type()&os.ModeSymlink != 0 {
			return fmt.Errorf("linked archive input")
		}
		if !d.IsDir() {
			info, e := d.Info()
			if e != nil || !info.Mode().IsRegular() {
				return fmt.Errorf("nonregular archive input")
			}
			rel, e := filepath.Rel(source, path)
			if e != nil || modes[filepath.ToSlash(rel)] == 0 {
				return fmt.Errorf("unlisted archive member")
			}
			paths = append(paths, path)
		}
		return nil
	})
	if e != nil {
		return e
	}
	if len(paths) != len(modes) {
		return fmt.Errorf("missing archive inventory member")
	}
	sort.Strings(paths)
	var b bytes.Buffer
	writer := zip.NewWriter(&b)
	for _, path := range paths {
		rel, _ := filepath.Rel(source, path)
		name := filepath.ToSlash(rel)
		data, e := regularRead(source, name)
		if e != nil {
			return e
		}
		if record := records[name]; record != nil && (digest(data) != record["sha256"] || jsonToken(record["size"]) != fmt.Sprint(len(data))) {
			return fmt.Errorf("archive inventory hash or size mismatch")
		}
		header := &zip.FileHeader{Name: name, Method: zip.Deflate}
		header.SetMode(modes[name])
		header.SetModTime(time.Date(1980, 1, 1, 0, 0, 0, 0, time.UTC))
		entry, e := writer.CreateHeader(header)
		if e != nil {
			return e
		}
		if _, e = entry.Write(data); e != nil {
			return e
		}
	}
	if e = writer.Close(); e != nil {
		return e
	}
	return writeData(destination, b.Bytes(), 0644)
}

// CheckNativeRelease distinguishes local package evidence from production
// qualification: clean source, exact target execution and external signatures
// are required. Cross-compilation never grants release qualification.
func CheckNativeRelease(root, path, target string, out io.Writer) error {
	manifest, e := VerifyPackage(path, "bundle-manifest.json")
	if e != nil {
		return e
	}
	if manifest["target"] != target {
		return fmt.Errorf("target mismatch")
	}
	if manifest["dirty_tree"] != false {
		return fmt.Errorf("release source was dirty")
	}
	commit, e := gitOutput(root, "rev-parse", "HEAD")
	if e != nil || strings.TrimSpace(commit) != manifest["source_git_commit"] {
		return fmt.Errorf("release source identity mismatch")
	}
	current, e := gitOutput(root, "status", "--porcelain")
	if e != nil || strings.TrimSpace(current) != "" {
		return fmt.Errorf("release checkout must be clean")
	}
	if e = requireNativeExecution(target, runtime.GOOS, runtime.GOARCH); e != nil {
		return e
	}
	binary := "opensocrates"
	if windowsNativeTarget(target) {
		binary += ".exe"
	}
	helper := "opensocrates-update-helper"
	if windowsNativeTarget(target) {
		helper += ".exe"
	}
	for _, executable := range []string{binary, helper} {
		if e = verifyGoBinary(filepath.Join(path, "bin", executable), target); e != nil {
			return e
		}
	}
	commands := nativeReleaseCommands{
		verifyManager: verifyManagerSignature,
		verifyHelper:  verifyHelperSignature,
		version: func(path string) ([]byte, error) {
			return exec.Command(path, "--version").Output()
		},
	}
	if e = checkNativeReleaseExecutables(filepath.Join(path, "bin", binary), filepath.Join(path, "bin", helper), target, str(manifest["product_version"]), commands); e != nil {
		return e
	}
	fmt.Fprintln(out, "RELEASE_PLATFORM_INTEGRITY_OK; authenticated/live host evidence remains a separate gate")
	return nil
}
