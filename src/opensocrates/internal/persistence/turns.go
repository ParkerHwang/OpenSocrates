package persistence

import (
	"bytes"
	"crypto/rand"
	"encoding/json"
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/verification"
	"os"
	"path/filepath"
	"regexp"
)

var ErrTurnStore = errors.New("store_unavailable")
var ErrTurnConflict = errors.New("turn_state_conflict")

// TurnStore persists only the closed, content-free turn contract. The raw
// token is used solely to derive the HMAC address; it never reaches a file.
type TurnStore struct {
	Root string
	key  []byte
}

func NewTurnStore(root string) (*TurnStore, error)      { return openTurnStore(root, true) }
func ExistingTurnStore(root string) (*TurnStore, error) { return openTurnStore(root, false) }
func openTurnStore(root string, create bool) (*TurnStore, error) {
	if !filepath.IsAbs(root) {
		return nil, ErrTurnStore
	}
	if create {
		if e := Ensure(root); e != nil {
			return nil, e
		}
	} else if platform.Guard(root) != nil {
		return nil, ErrTurnStore
	}
	if create {
		lock, e := platform.Lock(filepath.Join(root, "installation.key.lock"))
		if e != nil {
			return nil, e
		}
		defer lock.Close()
	}
	path := filepath.Join(root, "installation.key")
	var key []byte
	info, e := os.Lstat(path)
	if os.IsNotExist(e) && create {
		key = make([]byte, 32)
		if _, e = rand.Read(key); e != nil {
			return nil, ErrTurnStore
		}
		if e = platform.AtomicWrite(path, key, 0600); e != nil {
			return nil, e
		}
	} else {
		if e != nil || !info.Mode().IsRegular() {
			return nil, ErrTurnStore
		}
		key, e = platform.ReadFile(path, 32)
		if e != nil || len(key) != 32 {
			return nil, ErrTurnStore
		}
	}
	return &TurnStore{root, key}, nil
}
func (s *TurnStore) Key() []byte                           { return append([]byte{}, s.key...) }
func (s *TurnStore) TokenTag(token string) (string, error) { return domain.TokenTag(token, s.key) }
func (s *TurnStore) paths(tag string) (string, string, error) {
	if !regexp.MustCompile(`^sha256:[0-9a-f]{64}$`).MatchString(tag) {
		return "", "", ErrTurnStore
	}
	dir := filepath.Join(s.Root, "runtime", "turns")
	return filepath.Join(dir, tag[7:]+".json"), filepath.Join(dir, tag[7:]+".lock"), nil
}
func turnBytes(state map[string]any) ([]byte, error) {
	if e := domain.ValidateTurnState(state); e != nil {
		return nil, e
	}
	if e := verification.RejectPublic(state); e != nil {
		return nil, ErrTurnStore
	}
	b, e := contracts.CanonicalJSON(state)
	if e != nil || len(b) > domain.MaxTurnStateBytes {
		return nil, ErrTurnStore
	}
	return b, nil
}
func parseTurn(raw []byte) (map[string]any, error) {
	if len(raw) > domain.MaxTurnStateBytes {
		return nil, ErrTurnStore
	}
	v, e := contracts.Decode(raw)
	if e != nil {
		return nil, ErrTurnStore
	}
	m, ok := v.(map[string]any)
	if !ok || domain.ValidateTurnState(m) != nil || verification.RejectPublic(m) != nil {
		return nil, ErrTurnStore
	}
	return m, nil
}
func (s *TurnStore) Issue(state map[string]any) error {
	raw, e := turnBytes(state)
	if e != nil {
		return e
	}
	tag, _ := state["token_tag"].(string)
	path, lockPath, e := s.paths(tag)
	if e != nil {
		return e
	}
	lock, e := platform.Lock(lockPath)
	if e != nil {
		return e
	}
	defer lock.Close()
	if _, e = os.Lstat(path); !os.IsNotExist(e) {
		return ErrTurnConflict
	}
	return platform.AtomicWrite(path, raw, 0600)
}
func (s *TurnStore) Load(token string) (map[string]any, error) {
	tag, e := s.TokenTag(token)
	if e != nil {
		return nil, nil
	}
	return s.loadTag(tag)
}
func (s *TurnStore) loadTag(tag string) (map[string]any, error) {
	path, _, e := s.paths(tag)
	if e != nil {
		return nil, e
	}
	if _, e = os.Lstat(path); os.IsNotExist(e) {
		return nil, nil
	}
	raw, e := platform.ReadFile(path, domain.MaxTurnStateBytes)
	if e != nil {
		return nil, ErrTurnStore
	}
	m, e := parseTurn(raw)
	if e != nil || m["token_tag"] != tag {
		return nil, ErrTurnStore
	}
	return m, nil
}

// WithTurn serializes the entire control operation (including public record
// mutations), so concurrent same-token controls cannot both claim acceptance.
func (s *TurnStore) WithTurn(token string, change func(map[string]any) (map[string]any, bool, error)) error {
	tag, e := s.TokenTag(token)
	if e != nil {
		return e
	}
	_, lockPath, e := s.paths(tag)
	if e != nil {
		return e
	}
	lock, e := platform.Lock(lockPath)
	if e != nil {
		return e
	}
	defer lock.Close()
	state, e := s.loadTag(tag)
	if e != nil {
		return e
	}
	next, remove, e := change(state)
	if e != nil {
		return e
	}
	path, _, _ := s.paths(tag)
	if remove {
		return platform.Remove(path)
	}
	if next == nil {
		return nil
	}
	if next["token_tag"] != tag {
		return ErrTurnConflict
	}
	raw, e := turnBytes(next)
	if e != nil {
		return e
	}
	return platform.AtomicWrite(path, raw, 0600)
}
func (s *TurnStore) CompareAndSwap(expected, replacement map[string]any) error {
	a, e := turnBytes(expected)
	if e != nil {
		return e
	}
	b, e := turnBytes(replacement)
	if e != nil {
		return e
	}
	tag, _ := expected["token_tag"].(string)
	if replacement["token_tag"] != tag {
		return ErrTurnConflict
	}
	path, lockPath, e := s.paths(tag)
	if e != nil {
		return e
	}
	lock, e := platform.Lock(lockPath)
	if e != nil {
		return e
	}
	defer lock.Close()
	current, e := s.loadTag(tag)
	if e != nil || current == nil {
		return ErrTurnConflict
	}
	raw, _ := turnBytes(current)
	if !bytes.Equal(raw, a) {
		return ErrTurnConflict
	}
	return platform.AtomicWrite(path, b, 0600)
}
func (s *TurnStore) Delete(state map[string]any) error {
	if _, e := turnBytes(state); e != nil {
		return e
	}
	path, lockPath, e := s.paths(state["token_tag"].(string))
	if e != nil {
		return e
	}
	lock, e := platform.Lock(lockPath)
	if e != nil {
		return e
	}
	defer lock.Close()
	return platform.Remove(path)
}
func (s *TurnStore) SweepExpired(now string) (int, error) {
	if _, e := domain.ExpiryFor(now); e != nil {
		return 0, e
	}
	dir := filepath.Join(s.Root, "runtime", "turns")
	if e := platform.Guard(dir); e != nil {
		return 0, e
	}
	entries, e := os.ReadDir(dir)
	if e != nil {
		return 0, e
	}
	count := 0
	for _, entry := range entries {
		if !regexp.MustCompile(`^[0-9a-f]{64}\.json$`).MatchString(entry.Name()) {
			continue
		}
		tag := "sha256:" + entry.Name()[:64]
		_, lockPath, _ := s.paths(tag)
		lock, e := platform.Lock(lockPath)
		if e != nil {
			continue
		}
		state, e := s.loadTag(tag)
		if e == nil && state != nil && state["expires_at"].(string) <= now {
			path, _, _ := s.paths(tag)
			if platform.Remove(path) == nil {
				count++
			}
		}
		lock.Close()
	}
	return count, nil
}

// RecordStore retains the released YYYY-MM/<ULID>.jsonl layout. A public event
// batch is serialized and replaced atomically, never appended piecemeal.
type RecordStore struct{ Root string }

var taskIDPattern = regexp.MustCompile(`^[0-7][0-9A-HJKMNP-TV-Z]{25}$`)

func (s RecordStore) recordPath(task string, createMonth string) (string, error) {
	if !taskIDPattern.MatchString(task) {
		return "", ErrTurnStore
	}
	dir := filepath.Join(s.Root, "records")
	if platform.Guard(dir) != nil {
		return "", ErrTurnStore
	}
	entries, e := os.ReadDir(dir)
	if e != nil {
		return "", ErrTurnStore
	}
	found := ""
	for _, entry := range entries {
		if !regexp.MustCompile(`^[0-9]{4}-[0-9]{2}$`).MatchString(entry.Name()) {
			continue
		}
		monthDir := filepath.Join(dir, entry.Name())
		if platform.Guard(monthDir) != nil {
			return "", ErrTurnStore
		}
		path := filepath.Join(monthDir, task+".jsonl")
		if _, e = os.Lstat(path); e == nil {
			if found != "" {
				return "", ErrTurnStore
			}
			found = path
		} else if !os.IsNotExist(e) {
			return "", ErrTurnStore
		}
	}
	if found != "" {
		return found, nil
	}
	if createMonth == "" {
		return "", nil
	}
	if !regexp.MustCompile(`^[0-9]{4}-[0-9]{2}$`).MatchString(createMonth) {
		return "", ErrTurnStore
	}
	monthDir := filepath.Join(dir, createMonth)
	if e = platform.Mkdir(monthDir); e != nil {
		return "", e
	}
	return filepath.Join(monthDir, task+".jsonl"), nil
}
func (s RecordStore) Events(task string) ([]map[string]any, error) {
	if task == "" {
		return []map[string]any{}, nil
	}
	path, e := s.recordPath(task, "")
	if e != nil {
		return nil, e
	}
	if path == "" {
		return []map[string]any{}, nil
	}
	raw, e := platform.ReadFile(path, 100*1024*1024)
	if e != nil {
		return nil, ErrTurnStore
	}
	return parseRecords(task, raw)
}
func parseRecords(task string, raw []byte) ([]map[string]any, error) {
	events := []map[string]any{}
	if len(raw) > 0 && raw[len(raw)-1] != '\n' {
		return nil, ErrTurnStore
	}
	for _, line := range bytes.Split(raw, []byte{'\n'}) {
		if len(line) == 0 {
			continue
		}
		if len(line) > 64*1024 {
			return nil, ErrTurnStore
		}
		v, e := contracts.Decode(line)
		if e != nil {
			return nil, ErrTurnStore
		}
		m, ok := v.(map[string]any)
		if !ok || m["task_id"] != task || domain.ValidateRecord(m) != nil || verification.RejectPublic(m) != nil || validRecordCalculation(m) != nil {
			return nil, ErrTurnStore
		}
		sequence, ok := contracts.Int(m["sequence"])
		if !ok || sequence != int64(len(events)+1) {
			return nil, ErrTurnStore
		}
		events = append(events, m)
	}
	return events, nil
}
func (s RecordStore) AppendEvents(task string, events []map[string]any) error {
	if len(events) == 0 {
		return nil
	}
	timeText, _ := events[0]["occurred_at"].(string)
	if len(timeText) < 7 {
		return ErrTurnStore
	}
	path, e := s.recordPath(task, timeText[:7])
	if e != nil {
		return e
	}
	lock, e := platform.Lock(path[:len(path)-6] + ".lock")
	if e != nil {
		return e
	}
	defer lock.Close()
	var raw []byte
	if _, e = os.Lstat(path); e == nil {
		raw, e = platform.ReadFile(path, 100*1024*1024)
		if e != nil {
			return ErrTurnStore
		}
	} else if !os.IsNotExist(e) {
		return ErrTurnStore
	}
	prior, e := parseRecords(task, raw)
	if e != nil {
		return e
	}
	for _, event := range events {
		if event["task_id"] != task || domain.ValidateRecord(event) != nil || verification.RejectPublic(event) != nil || validRecordCalculation(event) != nil {
			return ErrTurnStore
		}
		seq, ok := contracts.Int(event["sequence"])
		if !ok || seq != int64(len(prior)+1) {
			return ErrTurnConflict
		}
		b, e := contracts.CanonicalJSON(event)
		if e != nil || len(b) > 64*1024 {
			return ErrTurnStore
		}
		raw = append(raw, b...)
		prior = append(prior, event)
	}
	if len(raw) > 100*1024*1024 {
		return ErrTurnStore
	}
	if _, e = domain.ReduceEvents(prior); e != nil {
		return ErrTurnStore
	}
	return platform.AtomicWrite(path, raw, 0600)
}

func validRecordCalculation(event map[string]any) error {
	payload, _ := event["payload"].(map[string]any)
	claim, _ := payload["claim_version"].(map[string]any)
	if claim["calculation"] == nil {
		return nil
	}
	raw, e := contracts.CanonicalCompact(claim["calculation"])
	if e != nil {
		return e
	}
	var c domain.Calculation
	if e = json.Unmarshal(raw, &c); e != nil {
		return e
	}
	return verification.ValidateStoredCalculation(c)
}
