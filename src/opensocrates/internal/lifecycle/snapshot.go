package lifecycle

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io/fs"
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"sort"
	"sync"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

const MaxFiles = 10000

// Released v1.5 Windows payloads include a 341,142,832-byte Codex executable.
// Adoption and rollback must accept that baseline while retaining finite limits.
const MaxFileBytes int64 = 512 << 20
const MaxTotalBytes int64 = 2 << 30

type Entry struct {
	Path      string `json:"path"`
	SHA256    string `json:"sha256,omitempty"`
	Mode      uint32 `json:"mode"`
	Directory bool   `json:"directory,omitempty"`
	Size      int64  `json:"size,omitempty"`
}
type Snapshot struct {
	Exists  bool    `json:"exists"`
	Entries []Entry `json:"entries"`
	SHA256  string  `json:"sha256"`
}

// Inspect binds ownership checks, all names, modes and bytes into a deterministic snapshot.
func Inspect(path string) (Snapshot, error) {
	if err := platform.GuardOwned(path); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return snapshot(false, []Entry{}), nil
		}
		return Snapshot{}, err
	}
	info, err := os.Lstat(path)
	if os.IsNotExist(err) {
		return snapshot(false, []Entry{}), nil
	}
	if err != nil {
		return Snapshot{}, diagnostics.New(diagnostics.Permission, "inventory")
	}
	if info.Mode()&os.ModeSymlink != 0 {
		return Snapshot{}, diagnostics.New(diagnostics.Permission, "inventory")
	}
	var entries []Entry
	var total int64
	add := func(p string, info fs.FileInfo) error {
		if len(entries) >= MaxFiles || (!info.IsDir() && !info.Mode().IsRegular()) {
			return diagnostics.New(diagnostics.Verification, "inventory")
		}
		if info.IsDir() {
			if err := platform.GuardOwned(p); err != nil {
				return err
			}
		}
		rel, e := filepath.Rel(path, p)
		if e != nil {
			return e
		}
		if rel == "." {
			rel = ""
		}
		row := Entry{Path: filepath.ToSlash(rel), Mode: uint32(portableInventoryMode(runtime.GOOS, p, info.Mode(), info.IsDir())), Directory: info.IsDir(), Size: info.Size()}
		if info.IsDir() {
			row.Size = 0
		} else {
			total += info.Size()
			if info.Size() > MaxFileBytes || total > MaxTotalBytes {
				return diagnostics.New(diagnostics.Verification, "inventory")
			}
			// SHA256File validates the regular leaf and its ancestors using the
			// same owned handle it hashes. Avoid a separate metadata-only check
			// of that leaf; directories still require their own ownership guard.
			hash, e := platform.SHA256File(p, MaxFileBytes)
			if e != nil {
				return e
			}
			row.SHA256 = hash
		}
		entries = append(entries, row)
		return nil
	}
	if info.IsDir() {
		err = filepath.WalkDir(path, func(p string, d fs.DirEntry, e error) error {
			if e != nil {
				return diagnostics.New(diagnostics.Permission, "inventory")
			}
			i, e := d.Info()
			if e != nil {
				return e
			}
			return add(p, i)
		})
	} else {
		err = add(path, info)
	}
	if err != nil {
		return Snapshot{}, err
	}
	sort.Slice(entries, func(i, j int) bool { return entries[i].Path < entries[j].Path })
	return snapshot(true, entries), nil
}
func snapshot(exists bool, entries []Entry) Snapshot {
	b, _ := json.Marshal(entries)
	h := sha256.Sum256(b)
	return Snapshot{Exists: exists, Entries: entries, SHA256: hex.EncodeToString(h[:])}
}
func Equal(a, b Snapshot) bool {
	return a.Exists == b.Exists && a.SHA256 == b.SHA256 && reflect.DeepEqual(a.Entries, b.Entries)
}
func copyVerified(from, to string, expected Snapshot) error {
	current, e := Inspect(from)
	if e != nil {
		return e
	}
	if !Equal(current, expected) || !current.Exists {
		return diagnostics.New(diagnostics.Verification, "stage")
	}
	absent, e := Inspect(to)
	if e != nil {
		return e
	}
	if absent.Exists {
		return diagnostics.New(diagnostics.Verification, "stage")
	}
	if e := copySnapshotEntries(from, to, current.Entries, platform.CopyOwnedFile); e != nil {
		return e
	}
	// Unix directory modes and Windows readonly attributes are preserved only
	// on the newly constructed, owner-checked staging tree.
	for i := len(current.Entries) - 1; i >= 0; i-- {
		entry := current.Entries[i]
		if entry.Directory {
			p := to
			if entry.Path != "" {
				p = filepath.Join(to, filepath.FromSlash(entry.Path))
			}
			if e := platform.SetOwnedMode(p, os.FileMode(entry.Mode)); e != nil {
				return diagnostics.New(diagnostics.Permission, "stage")
			}
		}
	}
	staged, e := Inspect(to)
	if e != nil {
		return e
	}
	if !Equal(staged, current) {
		return diagnostics.New(diagnostics.Verification, "stage")
	}
	again, e := Inspect(from)
	if e != nil {
		return e
	}
	if !Equal(again, current) {
		return diagnostics.New(diagnostics.Verification, "stage")
	}
	return nil
}

const ownedCopyWorkers = 4

// A job reservation and a recorded failure share one lock: after a failure is
// recorded, only already reserved jobs may finish. Partial owned objects remain
// available to the transaction's recovery path.
type ownedCopyQueue struct {
	mu    sync.Mutex
	files []Entry
	next  int
	err   error
}

func (q *ownedCopyQueue) claim() (Entry, bool) {
	q.mu.Lock()
	defer q.mu.Unlock()
	if q.err != nil || q.next >= len(q.files) {
		return Entry{}, false
	}
	entry := q.files[q.next]
	q.next++
	return entry, true
}

func (q *ownedCopyQueue) failed(err error) {
	q.mu.Lock()
	defer q.mu.Unlock()
	if q.err == nil {
		q.err = err
	}
}

// copySnapshotEntries accepts only the already inspected snapshot. Directories
// are constructed serially before disjoint regular leaves enter the fixed pool.
// The injected copy function is local to the call; production always uses the
// unchanged owner-checked, durable platform.CopyOwnedFile operation.
func copySnapshotEntries(from, to string, entries []Entry, copyFile func(string, string, int64, os.FileMode) error) error {
	files := make([]Entry, 0, len(entries))
	for _, entry := range entries {
		if !entry.Directory {
			files = append(files, entry)
			continue
		}
		target := to
		if entry.Path != "" {
			target = filepath.Join(to, filepath.FromSlash(entry.Path))
		}
		if err := platform.Mkdir(target); err != nil {
			return err
		}
	}
	copyEntry := func(entry Entry) error {
		source, target := from, to
		if entry.Path != "" {
			source = filepath.Join(from, filepath.FromSlash(entry.Path))
			target = filepath.Join(to, filepath.FromSlash(entry.Path))
		}
		return copyFile(source, target, MaxFileBytes, os.FileMode(entry.Mode))
	}
	if len(files) == 0 {
		return nil
	}
	if len(files) == 1 {
		return copyEntry(files[0])
	}
	queue := ownedCopyQueue{files: files}
	workers := min(ownedCopyWorkers, len(files))
	var joined sync.WaitGroup
	joined.Add(workers)
	for i := 0; i < workers; i++ {
		go func() {
			defer joined.Done()
			for {
				entry, ok := queue.claim()
				if !ok {
					return
				}
				if err := copyEntry(entry); err != nil {
					queue.failed(err)
					return
				}
			}
		}()
	}
	joined.Wait()
	return queue.err
}

// CopyVerified copies only a bound, owned regular tree and verifies both ends.
func CopyVerified(from, to string, expected Snapshot) error { return copyVerified(from, to, expected) }

// portableInventoryMode records Windows's readonly attribute and supported
// directory/file distinction without treating its synthetic 0666/0777 bits
// as ACL authority. A Windows file has no POSIX execute bit: its name and
// transaction aliases must never change its snapshot identity.
// Every caller has already validated ownership, DACLs and reparse boundaries.
// Unix modes remain exact; no existing source or foreign object is chmodded.
func portableInventoryMode(goos, _ string, mode os.FileMode, directory bool) os.FileMode {
	if goos != "windows" {
		return mode.Perm()
	}
	portable := os.FileMode(0644)
	if directory {
		portable = 0755
	}
	if mode.Perm()&0200 == 0 {
		portable &^= 0222
	}
	return portable
}
