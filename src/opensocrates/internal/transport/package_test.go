package transport

import "testing"

func TestSafeRelativeAcrossWindowsAndUnicode(t *testing.T) {
	for _, p := range []string{"../x", "/abs", "a\\b", "C:x", "a//b", "a/../b", "a/CON.md", "a/com1.txt", "a/trailing.", "a/trailing ", "a/\x00"} {
		if SafeRelative(p) {
			t.Fatalf("unsafe name accepted: %q", p)
		}
	}
	for _, p := range []string{"skills/한글/😀.md", ".agents/rules/opensocrates.md", "runtime/windows-x64/opensocrates.exe"} {
		if !SafeRelative(p) {
			t.Fatalf("safe name rejected: %q", p)
		}
	}
}
func FuzzSafeRelative(f *testing.F) {
	for _, p := range []string{"normal/file.md", "../../escape", "a\\b", "😀/한글.md"} {
		f.Add(p)
	}
	f.Fuzz(func(t *testing.T, p string) {
		if SafeRelative(p) {
			if p == "" {
				t.Fatal("empty accepted")
			}
			for _, part := range []string{"../", "\\", "\x00"} {
				for i := 0; i+len(part) <= len(p); i++ {
					if p[i:i+len(part)] == part {
						t.Fatalf("unsafe fragment accepted: %q", p)
					}
				}
			}
		}
	})
}
func TestManifestRevisionPrecisionAndPresence(t *testing.T) {
	for _, tc := range []struct {
		raw, want string
		invalid   bool
	}{{`{"content_revision":9007199254740993}`, "9007199254740993", false}, {`{"content_revision":3}`, "3", false}, {`{"content_revision":"frozen"}`, "frozen", false}, {`{"content_revision":null}`, "", true}, {`{}`, "", true}, {`{"content_revision":3.0}`, "", true}} {
		var manifest Manifest
		e := manifest.UnmarshalJSON([]byte(tc.raw))
		if (e != nil) != tc.invalid || !tc.invalid && manifest.ContentRevision != tc.want {
			t.Fatalf("revision %s: %q %v", tc.raw, manifest.ContentRevision, e)
		}
	}
}
func TestInventoryNullAndNumericPrecisionRefused(t *testing.T) {
	for _, raw := range []string{`{"path":"f","sha256":"x","size":null}`, `{"path":"f","sha256":"x","size":1.0}`, `{"path":"f","sha256":"x","mode":null}`, `{"path":"f","sha256":"x","mode":511}`} {
		var file File
		if e := file.UnmarshalJSON([]byte(raw)); e == nil {
			t.Fatalf("invalid inventory %s accepted", raw)
		}
	}
	var empty File
	if e := empty.UnmarshalJSON([]byte(`{"path":"f","sha256":"x","size":0,"mode":420}`)); e != nil || !empty.hasSize || empty.Size != 0 {
		t.Fatal("zero-sized file lost presence")
	}
}
