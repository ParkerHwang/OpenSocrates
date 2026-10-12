package platform

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"golang.org/x/text/unicode/norm"
	"io"
	"os"
	"path"
	"path/filepath"
	"strings"
	"unicode"
	"unicode/utf8"
)

type ArchiveLimits struct {
	MaxEntries                  int
	MaxFileBytes, MaxTotalBytes int64
}
type ArchiveEntry struct {
	Name      string
	Size      int64
	Mode      os.FileMode
	SHA256    string
	Directory bool
}

func DefaultArchiveLimits() ArchiveLimits {
	return ArchiveLimits{MaxEntries: 20000, MaxFileBytes: 128 << 20, MaxTotalBytes: 512 << 20}
}
func limitsValid(l ArchiveLimits) bool {
	return l.MaxEntries > 0 && l.MaxEntries <= 100000 && l.MaxFileBytes > 0 && l.MaxTotalBytes >= l.MaxFileBytes && l.MaxTotalBytes <= 2<<30
}
func reservedName(s string) bool {
	s = strings.NewReplacer("¹", "1", "²", "2", "³", "3").Replace(s)
	base := strings.ToUpper(strings.SplitN(s, ".", 2)[0])
	switch base {
	case "CON", "PRN", "AUX", "NUL", "CLOCK$", "CONIN$", "CONOUT$":
		return true
	}
	if len(base) == 4 && (strings.HasPrefix(base, "COM") || strings.HasPrefix(base, "LPT")) && strings.ContainsRune("123456789¹²³", rune(base[3])) {
		return true
	}
	return false
}
func archiveName(s string, dir bool) (string, error) {
	if !utf8.ValidString(s) || s == "" || strings.HasPrefix(s, "/") || strings.ContainsAny(s, "\\:\x00<>\"|?*") || strings.ContainsRune(s, '\uFFFD') {
		return "", invalidArchive()
	}
	if dir {
		s = strings.TrimSuffix(s, "/")
	}
	if s == "" || path.Clean(s) != s || len(s) > 4096 {
		return "", invalidArchive()
	}
	for _, p := range strings.Split(s, "/") {
		if p == "" || p == "." || p == ".." || strings.TrimRight(p, " .") != p || reservedName(p) {
			return "", invalidArchive()
		}
		for _, r := range p {
			if unicode.IsControl(r) {
				return "", invalidArchive()
			}
		}
	}
	return s, nil
}
func archiveKey(s string) string {
	return strings.Map(func(r rune) rune {
		least := r
		for n := unicode.SimpleFold(r); n != r; n = unicode.SimpleFold(n) {
			if n < least {
				least = n
			}
		}
		return least
	}, norm.NFD.String(s))
}

type archiveScan struct {
	limits  ArchiveLimits
	entries []ArchiveEntry
	names   map[string]bool
	total   int64
	visit   func(ArchiveEntry, []byte) error
}

func (s *archiveScan) add(name string, size int64, mode os.FileMode, dir bool, r io.Reader) error {
	name, e := archiveName(name, dir)
	if e != nil {
		return e
	}
	if len(s.entries) >= s.limits.MaxEntries || size < 0 || size > s.limits.MaxFileBytes || s.total > s.limits.MaxTotalBytes-size {
		return invalidArchive()
	}
	if mode&^(os.ModePerm|os.ModeDir) != 0 || (mode.IsDir() && !dir) {
		return invalidArchive()
	}
	if mode.Perm()&0022 != 0 {
		return invalidArchive()
	}
	key := archiveKey(name)
	if _, exists := s.names[key]; exists {
		return invalidArchive()
	}
	for parent := path.Dir(key); parent != "."; parent = path.Dir(parent) {
		if directory, exists := s.names[parent]; exists && !directory {
			return invalidArchive()
		}
	}
	if !dir {
		for existing := range s.names {
			if strings.HasPrefix(existing, key+"/") {
				return invalidArchive()
			}
		}
	}
	s.names[key] = dir
	entry := ArchiveEntry{Name: name, Size: size, Mode: mode.Perm(), Directory: dir}
	var data []byte
	if dir {
		if size != 0 {
			return invalidArchive()
		}
		entry.Mode = mode.Perm()
	} else {
		data, e = io.ReadAll(io.LimitReader(r, size+1))
		if e != nil || int64(len(data)) != size {
			return invalidArchive()
		}
		sum := sha256.Sum256(data)
		entry.SHA256 = hex.EncodeToString(sum[:])
		s.total += size
	}
	s.entries = append(s.entries, entry)
	if s.visit != nil {
		return s.visit(entry, data)
	}
	return nil
}
func scanArchive(archive string, l ArchiveLimits, visit func(ArchiveEntry, []byte) error) ([]ArchiveEntry, error) {
	if !limitsValid(l) {
		return nil, invalidArchive()
	}
	f, e := openOwned(archive, os.O_RDONLY, 0)
	if e != nil {
		return nil, e
	}
	defer f.Close()
	st, e := f.Stat()
	if e != nil || st.Size() > l.MaxTotalBytes || st.Size() < 4 {
		return nil, invalidArchive()
	}
	s := archiveScan{limits: l, names: map[string]bool{}, visit: visit}
	magic := make([]byte, 4)
	if _, e = f.ReadAt(magic, 0); e != nil {
		return nil, invalidArchive()
	}
	if bytes.HasPrefix(magic, []byte("PK")) {
		z, e := zip.NewReader(f, st.Size())
		if e != nil {
			return nil, invalidArchive()
		}
		if len(z.File) > l.MaxEntries {
			return nil, invalidArchive()
		}
		for _, item := range z.File {
			if item.UncompressedSize64 > uint64(l.MaxFileBytes) {
				return nil, invalidArchive()
			}
			mode := item.Mode()
			dir := mode.IsDir()
			if mode.Perm() == 0 {
				mode |= 0600
			}
			r, e := item.Open()
			if e != nil {
				return nil, invalidArchive()
			}
			e = s.add(item.Name, int64(item.UncompressedSize64), mode, dir, r)
			closeErr := r.Close()
			if e != nil || closeErr != nil {
				return nil, invalidArchive()
			}
		}
	} else if magic[0] == 0x1f && magic[1] == 0x8b {
		gz, e := gzip.NewReader(f)
		if e != nil {
			return nil, invalidArchive()
		}
		defer gz.Close()
		tr := tar.NewReader(io.LimitReader(gz, l.MaxTotalBytes+int64(l.MaxEntries)*4096+1))
		for {
			h, e := tr.Next()
			if e == io.EOF {
				break
			}
			if e != nil {
				return nil, invalidArchive()
			}
			if h.Typeflag != tar.TypeReg && h.Typeflag != tar.TypeRegA && h.Typeflag != tar.TypeDir {
				return nil, invalidArchive()
			}
			if h.Mode&^int64(0777) != 0 {
				return nil, invalidArchive()
			}
			mode := os.FileMode(h.Mode)
			dir := h.Typeflag == tar.TypeDir
			if dir {
				mode |= os.ModeDir
			}
			for key := range h.PAXRecords {
				switch key {
				case "path", "size", "mtime", "atime", "ctime", "uname", "gname", "uid", "gid":
				default:
					return nil, invalidArchive()
				}
			}
			if e = s.add(h.Name, h.Size, mode, dir, tr); e != nil {
				return nil, e
			}
		}
		if _, e = io.Copy(io.Discard, io.LimitReader(gz, 1)); e != nil {
			return nil, invalidArchive()
		}
	} else {
		return nil, invalidArchive()
	}
	if len(s.entries) == 0 {
		return nil, invalidArchive()
	}
	return s.entries, nil
}
func VerifyArchive(archive string, l ArchiveLimits) ([]ArchiveEntry, error) {
	return scanArchive(archive, l, nil)
}

// ExtractArchive requires an empty private destination. It validates the entire
// inventory before writing, then revalidates the captured archive bytes during
// extraction. Failed candidates are never activated; transaction owns cleanup.
func ExtractArchive(archive, dest string, l ArchiveLimits) error {
	expected, e := VerifyArchive(archive, l)
	if e != nil {
		return e
	}
	if e = Mkdir(dest); e != nil {
		return e
	}
	children, e := os.ReadDir(dest)
	if e != nil || len(children) != 0 {
		return invalidArchive()
	}
	index := 0
	_, e = scanArchive(archive, l, func(entry ArchiveEntry, data []byte) error {
		if index >= len(expected) || entry != expected[index] {
			return invalidArchive()
		}
		index++
		target := filepath.Join(dest, filepath.FromSlash(entry.Name))
		if entry.Directory {
			if e := Mkdir(target); e != nil {
				return e
			}
			return chmodOwned(target, entry.Mode)
		}
		if e := Mkdir(filepath.Dir(target)); e != nil {
			return e
		}
		if _, e := os.Lstat(target); !os.IsNotExist(e) {
			return invalidArchive()
		}
		return AtomicWrite(target, data, entry.Mode)
	})
	if e != nil {
		return e
	}
	if index != len(expected) {
		return invalidArchive()
	}
	return nil
}
