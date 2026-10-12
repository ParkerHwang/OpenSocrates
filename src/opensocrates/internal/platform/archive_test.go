package platform

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"os"
	"path/filepath"
	"testing"
)

func zipFixture(t *testing.T, names []string) string {
	t.Helper()
	var b bytes.Buffer
	w := zip.NewWriter(&b)
	for _, name := range names {
		h := &zip.FileHeader{Name: name, Method: zip.Deflate}
		h.SetMode(0644)
		f, e := w.CreateHeader(h)
		if e != nil {
			t.Fatal(e)
		}
		f.Write([]byte("content"))
	}
	if e := w.Close(); e != nil {
		t.Fatal(e)
	}
	p := filepath.Join(privateTestDir(t), "fixture.zip")
	if e := AtomicWrite(p, b.Bytes(), 0600); e != nil {
		t.Fatal(e)
	}
	return p
}
func TestArchiveRejectsAliases(t *testing.T) {
	cases := [][]string{{"../escape"}, {"/absolute"}, {"dir\\child"}, {"runtime:stream"}, {"bad?name"}, {"bad*name"}, {"bad|name"}, {"CON.txt"}, {"COM¹.exe"}, {"file."}, {"file "}, {"File", "file"}, {"é", "e\u0301"}, {"file", "file/child"}, {"file/child", "file"}, {"safe", "safe"}}
	for _, names := range cases {
		t.Run(names[0], func(t *testing.T) {
			if _, e := VerifyArchive(zipFixture(t, names), DefaultArchiveLimits()); e == nil {
				t.Fatal("unsafe archive accepted")
			}
		})
	}
}
func TestArchiveInventoryAndExtraction(t *testing.T) {
	p := zipFixture(t, []string{"bin/opensocrates", "content/한글.md"})
	entries, e := VerifyArchive(p, DefaultArchiveLimits())
	if e != nil || len(entries) != 2 || entries[0].SHA256 == "" {
		t.Fatalf("inventory: %v", e)
	}
	dest := filepath.Join(privateTestDir(t), "extract")
	if e = ExtractArchive(p, dest, DefaultArchiveLimits()); e != nil {
		t.Fatal(e)
	}
	b, e := ReadOwnedFile(filepath.Join(dest, "content", "한글.md"), 100)
	if e != nil || string(b) != "content" {
		t.Fatal("extraction mismatch")
	}
	if ExtractArchive(p, dest, DefaultArchiveLimits()) == nil {
		t.Fatal("nonempty destination overwritten")
	}
	limit := DefaultArchiveLimits()
	limit.MaxEntries = 1
	if _, e = VerifyArchive(p, limit); e == nil {
		t.Fatal("entry bound ignored")
	}
	limit = DefaultArchiveLimits()
	limit.MaxFileBytes = 2
	if _, e = VerifyArchive(p, limit); e == nil {
		t.Fatal("file bound ignored")
	}
}
func TestArchiveRejectsLinks(t *testing.T) {
	var b bytes.Buffer
	gz := gzip.NewWriter(&b)
	w := tar.NewWriter(gz)
	if e := w.WriteHeader(&tar.Header{Name: "link", Typeflag: tar.TypeSymlink, Linkname: "outside", Mode: 0644}); e != nil {
		t.Fatal(e)
	}
	w.Close()
	gz.Close()
	p := filepath.Join(privateTestDir(t), "link.tar.gz")
	if e := AtomicWrite(p, b.Bytes(), 0600); e != nil {
		t.Fatal(e)
	}
	if _, e := VerifyArchive(p, DefaultArchiveLimits()); e == nil {
		t.Fatal("tar link accepted")
	}
	var z bytes.Buffer
	zw := zip.NewWriter(&z)
	h := &zip.FileHeader{Name: "link"}
	h.SetMode(os.ModeSymlink | 0777)
	f, _ := zw.CreateHeader(h)
	f.Write([]byte("outside"))
	zw.Close()
	p = filepath.Join(privateTestDir(t), "link.zip")
	AtomicWrite(p, z.Bytes(), 0600)
	if _, e := VerifyArchive(p, DefaultArchiveLimits()); e == nil {
		t.Fatal("zip link accepted")
	}
}
func FuzzArchivePath(f *testing.F) {
	for _, name := range []string{"safe/한글.md", "../escape", "CON", "dir\\x", "a:b", "é", "e\u0301"} {
		f.Add(name)
	}
	f.Fuzz(func(t *testing.T, name string) {
		normalized, e := archiveName(name, false)
		if e == nil {
			if normalized != name || normalized == "" {
				t.Fatal("invalid successful normalization")
			}
			if _, e = archiveName(normalized, false); e != nil {
				t.Fatal("valid name not stable")
			}
		}
	})
}
