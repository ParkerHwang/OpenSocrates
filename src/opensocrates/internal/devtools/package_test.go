package devtools

import (
	"archive/zip"
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestContentPackagesAndPortableExport(t *testing.T) {
	root := generatorRepository(t)
	for _, host := range []string{"claude-chat", "antigravity"} {
		t.Run(host, func(t *testing.T) {
			output := filepath.Join(t.TempDir(), host)
			manifest, e := GeneratePlugin(root, host, "darwin-arm64", "", output)
			if e != nil {
				t.Fatal(e)
			}
			relative := "release-manifest.json"
			if host == "claude-chat" {
				relative = "opensocrates/release-manifest.json"
			}
			if _, e = VerifyPackage(output, relative); e != nil {
				t.Fatal(e)
			}
			if len(arr(manifest["canonical_methods"])) != 96 {
				t.Fatal("missing bilingual methods")
			}
			archive := filepath.Join(t.TempDir(), "skill.zip")
			if e = WritePortableZIP(output, archive); e != nil {
				t.Fatal(e)
			}
			first, e := os.ReadFile(archive)
			if e != nil {
				t.Fatal(e)
			}
			if e = WritePortableZIP(output, archive); e != nil {
				t.Fatal(e)
			}
			second, e := os.ReadFile(archive)
			if e != nil || !bytes.Equal(first, second) {
				t.Fatal("nondeterministic export")
			}
			reader, e := zip.OpenReader(archive)
			if e != nil {
				t.Fatal(e)
			}
			defer reader.Close()
			for _, member := range reader.File {
				if !member.Mode().IsRegular() || member.Mode().Perm() != 0644 {
					t.Fatal("nonportable content member", member.Name)
				}
			}
			inventory := arr(manifest["files"])
			path := str(obj(inventory[0])["path"])
			if e = os.WriteFile(filepath.Join(output, filepath.FromSlash(path)), []byte("foreign modified content"), 0644); e != nil {
				t.Fatal(e)
			}
			if _, e = GeneratePlugin(root, host, "darwin-arm64", "", output); e == nil {
				t.Fatal("overwrote modified package")
			}
		})
	}
}
func TestNativeProfileBoundaries(t *testing.T) {
	root := generatorRepository(t)
	for _, target := range []string{"windows-x64", "windows-arm64"} {
		if _, e := GeneratePlugin(root, "claude", target, "", filepath.Join(t.TempDir(), "claude")); e == nil {
			t.Fatal("added Windows Claude")
		}
	}
	out := filepath.Join(t.TempDir(), "codex")
	manifest, e := GeneratePlugin(root, "codex", "windows-x64", "", out)
	if e != nil {
		t.Fatal(e)
	}
	if len(arr(manifest["runtime_targets"])) != 0 {
		t.Fatal("claimed nonexistent runtime")
	}
	b, e := os.ReadFile(filepath.Join(out, "hooks/hooks.json"))
	if e != nil {
		t.Fatal(e)
	}
	if bytes.Contains(b, []byte("node")) || bytes.Contains(b, []byte("launch.sh")) || !bytes.Contains(b, []byte("opensocrates.exe")) {
		t.Fatal("non-native hook")
	}
}

func TestNativeDecisionReferenceTransport(t *testing.T) {
	root := generatorRepository(t)
	for _, target := range []string{"darwin-arm64", "windows-x64", "windows-arm64"} {
		output := filepath.Join(t.TempDir(), target)
		if _, e := GeneratePlugin(root, "codex", target, "", output); e != nil {
			t.Fatal(e)
		}
		for _, locale := range []string{"en", "ko"} {
			b, e := os.ReadFile(filepath.Join(output, "skills/opensocrates/references/decision/guide."+locale+".md"))
			if e != nil {
				t.Fatal(e)
			}
			text := string(b)
			for _, unsupported := range []string{"python -m", "launch.sh", "launch.mjs", "decision codex", "decision claude", "decision <host>"} {
				if strings.Contains(text, unsupported) {
					t.Errorf("generated reference requires old transport: %s", unsupported)
				}
			}
			if !strings.Contains(text, "\" decision --stream") {
				t.Fatal("native volatile session reference missing")
			}
			if windowsNativeTarget(target) && !strings.Contains(text, "`& \"./runtime/"+target+"/opensocrates.exe\" decision") {
				t.Fatal("PowerShell invocation missing")
			}
		}
	}
}

func TestWindowsARM64NativeProfile(t *testing.T) {
	root := generatorRepository(t)
	output := filepath.Join(t.TempDir(), "arm64")
	_, err := GeneratePlugin(root, "codex", "windows-arm64", "", output)
	if err != nil {
		t.Fatal(err)
	}
	manifest, err := ReadObject(filepath.Join(output, "release-manifest.json"))
	if err != nil {
		t.Fatal(err)
	}
	if manifest["shell_requirement"] != "powershell" || strings.Join(manifestStrings(manifest["release_targets"]), ",") != "windows-arm64" {
		t.Fatal("native ARM64 platform or shell metadata missing")
	}
	hooks, err := ReadObject(filepath.Join(output, "hooks/hooks.json"))
	if err != nil {
		t.Fatal(err)
	}
	for event, handlers := range obj(hooks["hooks"]) {
		for _, handler := range arr(handlers) {
			for _, raw := range arr(obj(handler)["hooks"]) {
				command := str(obj(raw)["command"])
				if !strings.HasPrefix(command, `& "$env:PLUGIN_ROOT\runtime\windows-arm64\opensocrates.exe" hook codex `) || strings.Contains(command, "windows-x64") || !configuredHookMatches(command, "codex", "windows-arm64", event) {
					t.Fatal("ARM64 hook uses wrong executable or command", event)
				}
			}
		}
	}
	if codes, err := checkPackageTree(output); err != nil || len(codes) != 0 {
		t.Fatalf("ARM64 profile validation: %v %v", codes, err)
	}
}

func TestContentExportsEquivalentAcrossNativeTargets(t *testing.T) {
	root := generatorRepository(t)
	for _, host := range []string{"claude-chat", "antigravity"} {
		t.Run(host, func(t *testing.T) {
			var first []byte
			for _, target := range []string{"darwin-arm64", "windows-x64", "windows-arm64"} {
				output := filepath.Join(t.TempDir(), host)
				manifest, err := GeneratePlugin(root, host, target, "", output)
				if err != nil {
					t.Fatal(err)
				}
				if len(arr(manifest["runtime_targets"])) != 0 || len(arr(manifest["release_targets"])) != 0 {
					t.Fatal("content-only export gained platform/runtime dependency")
				}
				archive := filepath.Join(t.TempDir(), host+".zip")
				if err = WritePortableZIP(output, archive); err != nil {
					t.Fatal(err)
				}
				data, err := os.ReadFile(archive)
				if err != nil {
					t.Fatal(err)
				}
				if first == nil {
					first = data
				} else if !bytes.Equal(first, data) {
					t.Fatalf("content export differs by native target %s", target)
				}
			}
		})
	}
}
