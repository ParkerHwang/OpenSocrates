package devtools

import (
	"archive/zip"
	"bytes"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func nativeArchiveFixture(t *testing.T, requested ...string) (string, string) {
	t.Helper()
	target := "windows-x64"
	if len(requested) == 1 {
		target = requested[0]
	}
	source := t.TempDir()
	files := map[string][]byte{
		"bin/opensocrates.exe":                                   []byte("synthetic native executable"),
		"bin/opensocrates-update-helper.exe":                     []byte("synthetic Go replacement helper"),
		"packages/codex/runtime/" + target + "/opensocrates.exe": []byte("synthetic bundled runtime"),
		"packages/codex/README.md":                               []byte("synthetic portable data\n"),
	}
	modes := map[string]os.FileMode{}
	for name, data := range files {
		modes[name] = 0644
		if strings.HasSuffix(name, ".exe") {
			modes[name] = 0755
		}
		// Reproduce Windows's ordinary 0666 stat metadata on every test host.
		if err := writeData(filepath.Join(source, filepath.FromSlash(name)), data, 0666); err != nil {
			t.Fatal(err)
		}
	}
	manifest := map[string]any{"schema": "opensocrates.native-bundle/1.0.0", "target": target, "files": fileInventory(files, modes)}
	if err := writeJSON(filepath.Join(source, "bundle-manifest.json"), manifest); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(filepath.Join(source, "bundle-manifest.json"), 0666); err != nil {
		t.Fatal(err)
	}
	return source, filepath.Join(t.TempDir(), "native.zip")
}

func TestNativeArchivePortableInventoryModes(t *testing.T) {
	for _, target := range []string{"windows-x64", "windows-arm64"} {
		t.Run(target, func(t *testing.T) {
			source, archive := nativeArchiveFixture(t, target)
			if err := WritePortableZIP(source, archive); err != nil {
				t.Fatal(err)
			}
			if _, err := publicationBundleManifest(archive); err != nil {
				t.Fatalf("ZIP differs from its declared portable inventory: %v", err)
			}
			reader, err := zip.OpenReader(archive)
			if err != nil {
				t.Fatal(err)
			}
			defer reader.Close()
			for _, member := range reader.File {
				want := os.FileMode(0644)
				if strings.HasSuffix(member.Name, ".exe") {
					want = 0755
				}
				if !member.Mode().IsRegular() || member.Mode().Perm() != want {
					t.Fatalf("%s: portable mode %o, expected %o", member.Name, member.Mode().Perm(), want)
				}
			}
		})
	}
}

func TestNativeArchiveModeMismatchRejected(t *testing.T) {
	source, archive := nativeArchiveFixture(t)
	if err := WritePortableZIP(source, archive); err != nil {
		t.Fatal(err)
	}
	reader, err := zip.OpenReader(archive)
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	var tampered bytes.Buffer
	writer := zip.NewWriter(&tampered)
	for _, member := range reader.File {
		header := member.FileHeader
		if member.Name == "bin/opensocrates.exe" {
			header.SetMode(0644)
		}
		out, err := writer.CreateHeader(&header)
		if err != nil {
			t.Fatal(err)
		}
		in, err := member.Open()
		if err != nil {
			t.Fatal(err)
		}
		_, err = io.Copy(out, in)
		in.Close()
		if err != nil {
			t.Fatal(err)
		}
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	tamperedPath := filepath.Join(t.TempDir(), "wrong-mode.zip")
	if err := os.WriteFile(tamperedPath, tampered.Bytes(), 0644); err != nil {
		t.Fatal(err)
	}
	if _, err = publicationBundleManifest(tamperedPath); err == nil || err.Error() != "release_archive_mode_mismatch" {
		t.Fatalf("incorrect native ZIP mode accepted: %v", err)
	}
}

func TestArchiveRejectsUndeclaredModesAndChangedBytes(t *testing.T) {
	for _, mutation := range []string{"mode", "bytes", "unlisted", "missing"} {
		t.Run(mutation, func(t *testing.T) {
			source, archive := nativeArchiveFixture(t)
			switch mutation {
			case "mode":
				manifest, err := ReadObject(filepath.Join(source, "bundle-manifest.json"))
				if err != nil {
					t.Fatal(err)
				}
				obj(arr(manifest["files"])[0])["mode"] = 0666
				if err = writeJSON(filepath.Join(source, "bundle-manifest.json"), manifest); err != nil {
					t.Fatal(err)
				}
			case "bytes":
				if err := os.WriteFile(filepath.Join(source, "bin/opensocrates.exe"), []byte("foreign executable"), 0666); err != nil {
					t.Fatal(err)
				}
			case "unlisted":
				if err := os.WriteFile(filepath.Join(source, "foreign"), []byte("foreign data"), 0666); err != nil {
					t.Fatal(err)
				}
			case "missing":
				if err := os.Remove(filepath.Join(source, "bin/opensocrates.exe")); err != nil {
					t.Fatal(err)
				}
			}
			if err := WritePortableZIP(source, archive); err == nil {
				t.Fatal("invalid portable archive source accepted")
			}
		})
	}
}
