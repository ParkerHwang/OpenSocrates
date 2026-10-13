package lifecycle

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

func waitCopySignal(t *testing.T, signal <-chan struct{}) {
	t.Helper()
	select {
	case <-signal:
	case <-time.After(10 * time.Second):
		t.Fatal("copy worker did not reach the controlled barrier")
	}
}

func TestCopySnapshotEntriesBoundsWorkersAndCreatesParentsFirst(t *testing.T) {
	root := privateLifecycleTestDir(t)
	destination := filepath.Join(root, "destination")
	entries := []Entry{{Directory: true, Mode: 0700}}
	for i := 0; i < 12; i++ {
		entries = append(entries, Entry{Path: fmt.Sprintf("nested/leaf-%02d", i), Mode: 0600})
	}
	// Even though the files precede this entry, no worker may run until every
	// owned parent has been created by the serial directory pass.
	entries = append(entries, Entry{Path: "nested", Directory: true, Mode: 0700})
	started, release := make(chan struct{}, len(entries)), make(chan struct{})
	var released sync.Once
	defer released.Do(func() { close(release) })
	var mu sync.Mutex
	active, peak, copied := 0, 0, 0
	done := make(chan error, 1)
	go func() {
		done <- copySnapshotEntries(root, destination, entries, func(_, target string, max int64, mode os.FileMode) error {
			if err := platform.GuardOwned(filepath.Dir(target)); err != nil {
				return fmt.Errorf("owned parent was not created before copy: %w", err)
			}
			if max != MaxFileBytes || mode != 0600 {
				return errors.New("copy limits or mode changed")
			}
			mu.Lock()
			active++
			peak = maxInt(peak, active)
			mu.Unlock()
			started <- struct{}{}
			<-release
			mu.Lock()
			active--
			copied++
			mu.Unlock()
			return nil
		})
	}()
	for i := 0; i < ownedCopyWorkers; i++ {
		waitCopySignal(t, started)
	}
	select {
	case <-started:
		t.Fatal("more than four copies entered before a worker was released")
	default:
	}
	released.Do(func() { close(release) })
	select {
	case err := <-done:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(10 * time.Second):
		t.Fatal("copy workers did not join")
	}
	if peak != ownedCopyWorkers || active != 0 || copied != 12 {
		t.Fatalf("worker bound or completion differs: peak=%d active=%d copied=%d", peak, active, copied)
	}
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}

func TestOwnedCopyQueueStopsReservationsAfterFirstRecordedError(t *testing.T) {
	first, later := errors.New("first bounded failure"), errors.New("later bounded failure")
	queue := ownedCopyQueue{files: make([]Entry, 10)}
	for i := 0; i < ownedCopyWorkers; i++ {
		if _, ok := queue.claim(); !ok {
			t.Fatal("initial worker reservation rejected")
		}
	}
	queue.failed(first)
	queue.failed(later)
	if _, ok := queue.claim(); ok || queue.next != ownedCopyWorkers {
		t.Fatal("new job reserved after a failure was recorded")
	}
	if !errors.Is(queue.err, first) {
		t.Fatal("later failure overwrote the first recorded failure")
	}
}

func TestCopySnapshotEntriesJoinsInflightAndPreservesOwnedPartialFiles(t *testing.T) {
	root := privateLifecycleTestDir(t)
	destination := filepath.Join(root, "destination")
	entries := []Entry{{Directory: true, Mode: 0700}}
	for i := 0; i < ownedCopyWorkers; i++ {
		entries = append(entries, Entry{Path: fmt.Sprintf("leaf-%d", i), Mode: 0600})
	}
	started, release, failed := make(chan struct{}, ownedCopyWorkers), make(chan struct{}), make(chan struct{})
	failRelease := make(chan struct{})
	var released, failureReleased sync.Once
	defer released.Do(func() { close(release) })
	defer failureReleased.Do(func() { close(failRelease) })
	sentinel := errors.New("injected copy failure")
	done := make(chan error, 1)
	go func() {
		done <- copySnapshotEntries(root, destination, entries, func(_, target string, _ int64, _ os.FileMode) error {
			if err := platform.ExclusiveWrite(target, []byte("owned partial bytes"), 0600); err != nil {
				return err
			}
			started <- struct{}{}
			if filepath.Base(target) == "leaf-0" {
				<-failRelease
				close(failed)
				return sentinel
			}
			<-release
			return nil
		})
	}()
	// Keep the failure-producing job blocked until all four are reserved, so
	// every other job is unambiguously in flight when the error occurs.
	for i := 0; i < ownedCopyWorkers; i++ {
		waitCopySignal(t, started)
	}
	failureReleased.Do(func() { close(failRelease) })
	waitCopySignal(t, failed)
	select {
	case <-done:
		t.Fatal("copy returned while other reserved files were still in flight")
	default:
	}
	released.Do(func() { close(release) })
	select {
	case err := <-done:
		if !errors.Is(err, sentinel) {
			t.Fatalf("copy failure not retained: %v", err)
		}
	case <-time.After(10 * time.Second):
		t.Fatal("copy did not join in-flight files after failure")
	}
	for i := 0; i < ownedCopyWorkers; i++ {
		bytes, err := platform.ReadFile(filepath.Join(destination, fmt.Sprintf("leaf-%d", i)), 100)
		if err != nil || string(bytes) != "owned partial bytes" {
			t.Fatalf("owned partial file removed or changed: %v", err)
		}
	}
}

func TestCopySnapshotEntriesZeroAndOneFilePaths(t *testing.T) {
	for _, count := range []int{0, 1} {
		t.Run(fmt.Sprint(count), func(t *testing.T) {
			root := privateLifecycleTestDir(t)
			destination := filepath.Join(root, "destination")
			entries := []Entry{{Directory: true, Mode: 0700}}
			if count == 1 {
				entries = append(entries, Entry{Path: "only.bin", Mode: 0600})
			}
			calls := 0
			sentinel := errors.New("single file error")
			err := copySnapshotEntries(root, destination, entries, func(source, target string, max int64, mode os.FileMode) error {
				calls++
				if source != filepath.Join(root, "only.bin") || target != filepath.Join(destination, "only.bin") || max != MaxFileBytes || mode != 0600 {
					t.Error("single file copy arguments differ")
				}
				return sentinel
			})
			if calls != count || (count == 0 && err != nil) || (count == 1 && !errors.Is(err, sentinel)) {
				t.Fatalf("zero/one-file path differs: calls=%d err=%v", calls, err)
			}
			if err := platform.GuardOwned(destination); err != nil {
				t.Fatal("zero/one-file directory was not created")
			}
		})
	}
}

func TestCopyVerifiedParallelTreePreservesSnapshotAndSource(t *testing.T) {
	root := privateLifecycleTestDir(t)
	source, destination := filepath.Join(root, "source"), filepath.Join(root, "destination")
	if err := platform.Mkdir(filepath.Join(source, "nested")); err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 20; i++ {
		mode := os.FileMode(0600)
		if i%2 == 0 {
			mode = 0644
		}
		path := filepath.Join(source, "nested", fmt.Sprintf("leaf-%02d", i))
		if err := platform.AtomicWrite(path, []byte(fmt.Sprintf("synthetic distinct payload %02d\n", i)), mode); err != nil {
			t.Fatal(err)
		}
	}
	expected, err := Inspect(source)
	if err != nil {
		t.Fatal(err)
	}
	if err := CopyVerified(source, destination, expected); err != nil {
		t.Fatal(err)
	}
	actual, err := Inspect(destination)
	if err != nil || !Equal(expected, actual) {
		t.Fatalf("parallel copy changed names, modes, sizes, bytes or snapshot identity: %v", err)
	}
	after, err := Inspect(source)
	if err != nil || !Equal(expected, after) {
		t.Fatalf("parallel copy mutated source: %v", err)
	}
}
