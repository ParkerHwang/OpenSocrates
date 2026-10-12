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
	if _, e := GeneratePlugin(root, "claude", "windows-x64", "", filepath.Join(t.TempDir(), "claude")); e == nil {
		t.Fatal("added Windows Claude")
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
	for _, target := range []string{"darwin-arm64", "windows-x64"} {
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
			if target == "windows-x64" && !strings.Contains(text, "`& \"./runtime/windows-x64/opensocrates.exe\" decision") {
				t.Fatal("PowerShell invocation missing")
			}
		}
	}
}
