package platform

import (
	"context"
	"encoding/json"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

// ReplacementRequest is a content-free, owned local capability. No secret or
// model input is accepted. Only the two first-party management EXEs are targets.
type ReplacementRequest struct {
	Schema          int    `json:"schema"`
	OperationID     string `json:"operation_id"`
	PID             int    `json:"pid"`
	Target          string `json:"target"`
	Candidate       string `json:"candidate"`
	Backup          string `json:"backup"`
	PreviousSHA256  string `json:"previous_sha256"`
	CandidateSHA256 string `json:"candidate_sha256"`
	HelperSHA256    string `json:"helper_sha256"`
	TimeoutSeconds  int    `json:"timeout_seconds"`
}
type replacementJournal struct {
	Schema          int    `json:"schema"`
	OperationID     string `json:"operation_id"`
	Stage           string `json:"stage"`
	PreviousSHA256  string `json:"previous_sha256"`
	CandidateSHA256 string `json:"candidate_sha256"`
}

var digestPattern = regexp.MustCompile(`^[0-9a-f]{64}$`)
var operationPattern = regexp.MustCompile(`^[0-9a-f]{32}$`)

func replacementFailure() error {
	return diagnostics.New(diagnostics.RollbackIncomplete, "replacement")
}
func decodeClosed(data []byte, out any) error {
	d := json.NewDecoder(strings.NewReader(string(data)))
	d.DisallowUnknownFields()
	if d.Decode(out) != nil {
		return failure()
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		return failure()
	}
	return nil
}
func hashEquals(path, expected string) bool {
	actual, e := SHA256File(path, 128<<20)
	return e == nil && actual == expected
}
func saveReplacement(path string, j replacementJournal) error {
	b, e := json.Marshal(j)
	if e != nil {
		return replacementFailure()
	}
	return AtomicWrite(path, append(b, '\n'), 0600)
}

// ReplaceExecutable is implemented by an independently running Go helper.
// Write-ahead stages and verified hashes make interrupted activation recoverable.
// Changed candidates, installed files or backups are preserved, never guessed.
func ReplaceExecutable(ctx context.Context, requestPath string) error {
	b, e := ReadFile(requestPath, 64<<10)
	if e != nil {
		return e
	}
	var r ReplacementRequest
	if decodeClosed(b, &r) != nil {
		return failure()
	}
	base := strings.ToLower(filepath.Base(r.Target))
	if r.Schema != 1 || !operationPattern.MatchString(r.OperationID) || r.PID < 0 || r.TimeoutSeconds < 1 || r.TimeoutSeconds > 120 || !digestPattern.MatchString(r.PreviousSHA256) || !digestPattern.MatchString(r.CandidateSHA256) || !digestPattern.MatchString(r.HelperSHA256) || (base != "opensocrates.exe" && base != "opensocrates-update-helper.exe") {
		return failure()
	}
	paths := []string{r.Target, r.Candidate, r.Backup}
	for _, p := range paths {
		if _, e = cleanPath(p); e != nil {
			return e
		}
	}
	if r.Target == r.Candidate || r.Target == r.Backup || r.Candidate == r.Backup {
		return failure()
	}
	// The request and recovery copy must live alongside the stable target. The
	// candidate may be in a versioned child directory of that owned root.
	root := filepath.Dir(r.Target)
	if filepath.Dir(r.Backup) != root || filepath.Dir(requestPath) != root {
		return failure()
	}
	relative, e := filepath.Rel(root, r.Candidate)
	if e != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(os.PathSeparator)) {
		return failure()
	}
	self, e := os.Executable()
	if e != nil || strings.EqualFold(self, r.Target) || !hashEquals(self, r.HelperSHA256) {
		return failure()
	}
	lock, e := Lock(filepath.Join(root, "replacement.lock"))
	if e != nil {
		return e
	}
	defer lock.Close()
	var leases []io.Closer
	for _, p := range paths {
		lease, e := Lease(p)
		if e != nil {
			for _, l := range leases {
				l.Close()
			}
			return e
		}
		leases = append(leases, lease)
	}
	defer func() {
		for _, l := range leases {
			l.Close()
		}
	}()
	journalPath := requestPath + ".journal"
	j := replacementJournal{Schema: 1, OperationID: r.OperationID, Stage: "prepared", PreviousSHA256: r.PreviousSHA256, CandidateSHA256: r.CandidateSHA256}
	if data, e := ReadFile(journalPath, 64<<10); e == nil {
		if decodeClosed(data, &j) != nil || j.Schema != 1 || j.OperationID != r.OperationID || j.PreviousSHA256 != r.PreviousSHA256 || j.CandidateSHA256 != r.CandidateSHA256 {
			return replacementFailure()
		}
	} else if _, statErr := os.Lstat(journalPath); !os.IsNotExist(statErr) {
		return replacementFailure()
	}
	// A previously activated target is accepted only with its intact recovery copy.
	if hashEquals(r.Target, r.CandidateSHA256) {
		if !hashEquals(r.Backup, r.PreviousSHA256) {
			return replacementFailure()
		}
		j.Stage = "verified"
		return saveReplacement(journalPath, j)
	}
	if _, e = os.Lstat(r.Target); os.IsNotExist(e) {
		if !hashEquals(r.Backup, r.PreviousSHA256) {
			return replacementFailure()
		}
		if e = Rename(r.Backup, r.Target); e != nil {
			return replacementFailure()
		}
		j.Stage = "rolled-back"
		if e = saveReplacement(journalPath, j); e != nil {
			return e
		}
		return diagnostics.New(diagnostics.Activation, "replacement_rolled_back")
	}
	if !hashEquals(r.Target, r.PreviousSHA256) || !hashEquals(r.Candidate, r.CandidateSHA256) {
		return replacementFailure()
	}
	if _, e = os.Lstat(r.Backup); !os.IsNotExist(e) {
		return replacementFailure()
	}
	bounded, cancel := context.WithTimeout(ctx, time.Duration(r.TimeoutSeconds)*time.Second)
	defer cancel()
	if e = waitOwnedProcess(bounded, r.PID, r.Target); e != nil {
		return e
	}
	j.Stage = "backup-intent"
	if e = saveReplacement(journalPath, j); e != nil {
		return e
	}
	if e = Rename(r.Target, r.Backup); e != nil {
		return e
	}
	j.Stage = "activate-intent"
	if e = saveReplacement(journalPath, j); e != nil {
		return replacementFailure()
	}
	if !hashEquals(r.Backup, r.PreviousSHA256) || !hashEquals(r.Candidate, r.CandidateSHA256) {
		return replacementFailure()
	}
	if e = Rename(r.Candidate, r.Target); e != nil {
		if hashEquals(r.Backup, r.PreviousSHA256) {
			if restore := Rename(r.Backup, r.Target); restore == nil && hashEquals(r.Target, r.PreviousSHA256) {
				j.Stage = "rolled-back"
				saveReplacement(journalPath, j)
			}
		}
		return replacementFailure()
	}
	if !hashEquals(r.Target, r.CandidateSHA256) || !hashEquals(r.Backup, r.PreviousSHA256) {
		return replacementFailure()
	}
	j.Stage = "verified"
	return saveReplacement(journalPath, j)
}

// WaitOwnedProcess waits only for the specified owned first-party executable.
// A missing PID is already exited; a mismatched live image is never waited on.
func WaitOwnedProcess(ctx context.Context, pid int, target string) error {
	if pid < 1 {
		return failure()
	}
	if e := GuardOwned(target); e != nil {
		return e
	}
	if _, ok := ctx.Deadline(); !ok {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, 120*time.Second)
		defer cancel()
	}
	return waitOwnedProcess(ctx, pid, target)
}
