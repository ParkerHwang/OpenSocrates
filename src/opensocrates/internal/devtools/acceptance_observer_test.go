package devtools

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

func acceptanceObserverFixture(t *testing.T) string {
	t.Helper()
	root, err := platform.MkdirTemp("", "opensocrates-native-acceptance-observer-")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(root) })
	for _, relative := range []string{"home/.opensocrates/transactions", "codex"} {
		if err := platform.Mkdir(filepath.Join(root, filepath.FromSlash(relative))); err != nil {
			t.Fatal(err)
		}
	}
	return root
}

func acceptanceObserverWrite(t *testing.T, path string, value any) []byte {
	t.Helper()
	data, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	if err = platform.AtomicWrite(path, data, 0600); err != nil {
		t.Fatal(err)
	}
	return data
}

func TestAcceptanceInstallFailureObservationRedactsAndDoesNotMutate(t *testing.T) {
	root := acceptanceObserverFixture(t)
	secret := "PRIVATE-ACCOUNT-TOKEN-AND-PROMPT"
	state := filepath.Join(root, "home/.opensocrates")
	if err := platform.Mkdir(filepath.Join(state, ".management-unknown-name/host/build/generated/plugins/codex")); err != nil {
		t.Fatal(err)
	}
	acceptanceObserverWrite(t, filepath.Join(state, "native-state.json"), map[string]any{"secret": secret})
	journalPath := filepath.Join(state, "transactions/0123456789abcdef0123456789abcdef.json")
	journal := acceptanceObserverWrite(t, journalPath, map[string]any{"schema": lifecycle.JournalSchema, "stage": "applying", "registration_started": true, "id": secret, "action": secret, "files": []any{map[string]any{"target": root + secret, "source": secret, "phase": "planned"}}, "lock_identity": secret})
	registrationPath := filepath.Join(root, "codex/host-fixture.json")
	registration := acceptanceObserverWrite(t, registrationPath, map[string]any{"installed": true, "enabled": false, "marketplace": root + secret, "extra": secret})
	actual := acceptanceInstallFailureObservation(root)
	for key, want := range map[string]any{"fixture_scope_status": "available", "state_dir_status": "present", "management_preparation_count": 1, "management_preparation_status": "present", "management_host_status": "present", "management_payload_status": "present", "native_state_status": "present", "active_state_status": "absent", "journal_count": 1, "journal_status": "available", "last_transaction_stage": "applying", "registration_started_status": "available", "registration_started": true, "file_operations_status": "available", "file_operation_count": 1, "planned_operation_count": 1, "prepared_operation_count": 0, "next_planned_operation_index": 0, "synthetic_registration_status": "available", "synthetic_installed": true, "synthetic_enabled": false, "synthetic_marketplace_nonempty": true} {
		if actual[key] != want {
			t.Errorf("%s=%v want %v", key, actual[key], want)
		}
	}
	output, err := json.Marshal(actual)
	encodedRoot, _ := json.Marshal(root)
	if err != nil || bytes.Contains(output, encodedRoot) || strings.Contains(string(output), secret) || strings.Contains(string(output), "0123456789abcdef") || strings.Contains(string(output), ".management-unknown-name") {
		t.Fatal("observer exported private fixture data")
	}
	for path, original := range map[string][]byte{journalPath: journal, registrationPath: registration} {
		after, err := platform.ReadFile(path, 8<<20)
		if err != nil || !bytes.Equal(after, original) {
			t.Fatal("observer mutated fixture")
		}
	}
}

func TestAcceptanceInstallFailureObservationRejectsForeignScopeAndLinks(t *testing.T) {
	if actual := acceptanceInstallFailureObservation(t.TempDir()); actual["fixture_scope_status"] != "unavailable" {
		t.Fatal("nonfixture scope inspected")
	}
	root := acceptanceObserverFixture(t)
	// Guarding an invalid scope must happen before trying a user-controlled leaf.
	outside := t.TempDir()
	linked := filepath.Join(filepath.Dir(root), filepath.Base(root)+"-linked")
	if err := os.Symlink(outside, linked); err == nil {
		t.Cleanup(func() { os.Remove(linked) })
		if actual := acceptanceInstallFailureObservation(linked); actual["fixture_scope_status"] != "unavailable" {
			t.Fatal("linked fixture root inspected")
		}
	} else if runtime.GOOS != "windows" {
		t.Fatal(err)
	}
	journalPath := filepath.Join(root, "home/.opensocrates/transactions/0123456789abcdef0123456789abcdef.json")
	target := filepath.Join(outside, "private.json")
	if err := os.WriteFile(target, []byte(`{"schema":"opensocrates.lifecycle-journal/1.0.0","stage":"committed","registration_started":true}`), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(target, journalPath); err == nil {
		actual := acceptanceInstallFailureObservation(root)
		if actual["journal_status"] != "unavailable" || actual["last_transaction_stage"] != "unavailable" {
			t.Fatal("linked journal followed")
		}
	} else if runtime.GOOS != "windows" {
		t.Fatal(err)
	}
}

func TestAcceptanceInstallFailureObservationUnknownAndUnavailableAreDistinct(t *testing.T) {
	for _, scenario := range []struct {
		name          string
		value         any
		stage, status string
	}{
		{"unknown-stage", map[string]any{"schema": lifecycle.JournalSchema, "stage": "PRIVATE-ARBITRARY-TEXT", "registration_started": false}, "unknown", "available"},
		{"wrong-schema", map[string]any{"schema": "foreign", "stage": "applying", "registration_started": true}, "unavailable", "unavailable"},
		{"missing-fields", map[string]any{"schema": lifecycle.JournalSchema}, "unknown", "available"},
	} {
		t.Run(scenario.name, func(t *testing.T) {
			root := acceptanceObserverFixture(t)
			path := filepath.Join(root, "home/.opensocrates/transactions/0123456789abcdef0123456789abcdef.json")
			acceptanceObserverWrite(t, path, scenario.value)
			actual := acceptanceInstallFailureObservation(root)
			if actual["journal_status"] != scenario.status || actual["last_transaction_stage"] != scenario.stage {
				t.Fatal("uncertain journal converted to stage evidence")
			}
			output, _ := json.Marshal(actual)
			if bytes.Contains(output, []byte("PRIVATE-ARBITRARY-TEXT")) {
				t.Fatal("unknown stage leaked")
			}
		})
	}
	root := acceptanceObserverFixture(t)
	actual := acceptanceInstallFailureObservation(root)
	if actual["journal_count"] != 0 || actual["journal_status"] != "absent" || actual["last_transaction_stage"] != "none" || actual["synthetic_registration_status"] != "absent" {
		t.Fatal("absence reported as successful observation")
	}
}

func TestAcceptanceInstallFailureObservationDoesNotSelectLatestAndBoundsEnumeration(t *testing.T) {
	root := acceptanceObserverFixture(t)
	transactions := filepath.Join(root, "home/.opensocrates/transactions")
	for i := 0; i < 2; i++ {
		acceptanceObserverWrite(t, filepath.Join(transactions, fmt.Sprintf("%032x.json", i)), map[string]any{"schema": lifecycle.JournalSchema, "stage": "applying", "registration_started": true})
	}
	actual := acceptanceInstallFailureObservation(root)
	if actual["journal_count"] != 2 || actual["journal_status"] != "unknown" || actual["last_transaction_stage"] != "unknown" || actual["registration_started_status"] != "unavailable" {
		t.Fatal("multiple journals guessed as latest")
	}
	for i := 2; i < 17; i++ {
		acceptanceObserverWrite(t, filepath.Join(transactions, fmt.Sprintf("%032x.json", i)), map[string]any{"schema": lifecycle.JournalSchema, "stage": "committed"})
	}
	actual = acceptanceInstallFailureObservation(root)
	if actual["journal_count"] != -1 || actual["journal_status"] != "unknown" || actual["last_transaction_stage"] != "unknown" {
		t.Fatal("unbounded journal inventory inferred")
	}
}

func TestAcceptanceInstallFailureObservationBoundsPrivateReads(t *testing.T) {
	root := acceptanceObserverFixture(t)
	path := filepath.Join(root, "home/.opensocrates/transactions/0123456789abcdef0123456789abcdef.json")
	if err := platform.AtomicWrite(path, bytes.Repeat([]byte("x"), (8<<20)+1), 0600); err != nil {
		t.Fatal(err)
	}
	registration := filepath.Join(root, "codex/host-fixture.json")
	if err := platform.AtomicWrite(registration, bytes.Repeat([]byte("x"), (64<<10)+1), 0600); err != nil {
		t.Fatal(err)
	}
	actual := acceptanceInstallFailureObservation(root)
	if actual["journal_status"] != "unavailable" || actual["last_transaction_stage"] != "unavailable" || actual["synthetic_registration_status"] != "unavailable" {
		t.Fatal("oversize private data accepted")
	}
	if runtime.GOOS != "windows" {
		acceptanceObserverWrite(t, path, map[string]any{"schema": lifecycle.JournalSchema, "stage": "committed"})
		if err := os.Chmod(path, 0644); err != nil {
			t.Fatal(err)
		}
		actual = acceptanceInstallFailureObservation(root)
		if actual["journal_status"] != "unavailable" {
			t.Fatal("nonprivate journal read")
		}
	}
}

func TestAcceptanceInstallFailureObservationBoundsPreparationEnumeration(t *testing.T) {
	root := acceptanceObserverFixture(t)
	state := filepath.Join(root, "home/.opensocrates")
	for i := 0; i < 16; i++ {
		acceptanceObserverWrite(t, filepath.Join(state, fmt.Sprintf("foreign-synthetic-%d", i)), map[string]any{"private": "DO-NOT-EXPORT"})
	}
	actual := acceptanceInstallFailureObservation(root)
	if actual["management_preparation_count"] != -1 || actual["management_preparation_status"] != "unknown" || actual["management_host_status"] != "unknown" || actual["management_payload_status"] != "unknown" {
		t.Fatal("capped directory enumeration inferred preparation absence")
	}
}

func TestAcceptanceInstallFailureObservationReportsOnlyBoundedOperationProgress(t *testing.T) {
	scenarios := []struct {
		name                           string
		files                          any
		status                         string
		count, planned, prepared, next int
	}{
		{"preparing-second-copy", []any{map[string]any{"phase": "prepared"}, map[string]any{"phase": "planned"}, map[string]any{"phase": "planned"}}, "available", 3, 2, 1, 1},
		{"preparing-first-copy", []any{map[string]any{"phase": "planned"}, map[string]any{"phase": "planned"}}, "available", 2, 2, 0, 0},
		{"all-prepared", []any{map[string]any{"phase": "prepared"}, map[string]any{"phase": "prepared"}}, "available", 2, 0, 2, -1},
		{"other-closed-engine-phases", []any{map[string]any{"phase": "backup-intent"}, map[string]any{"phase": "activate-intent"}, map[string]any{"phase": "applied"}, map[string]any{"phase": "restored"}, map[string]any{"phase": "cleanup-intent"}, map[string]any{"phase": "cleaned"}}, "available", 6, 0, 0, -1},
		{"unsupported-private-phase", []any{map[string]any{"phase": "PRIVATE-PHASE-TEXT"}}, "unknown", -1, -1, -1, -1},
		{"missing-phase", []any{map[string]any{"source": "PRIVATE-PHASE-TEXT"}}, "unavailable", -1, -1, -1, -1},
		{"mistyped-phase", []any{map[string]any{"phase": map[string]any{"private": "PRIVATE-PHASE-TEXT"}}}, "unavailable", -1, -1, -1, -1},
		{"nonobject-operation", []any{"PRIVATE-PHASE-TEXT"}, "unavailable", -1, -1, -1, -1},
		{"missing-operations", nil, "unavailable", -1, -1, -1, -1},
		{"empty-operations", []any{}, "unavailable", -1, -1, -1, -1},
		{"mistyped-operations", "PRIVATE-PHASE-TEXT", "unavailable", -1, -1, -1, -1},
	}
	for _, scenario := range scenarios {
		t.Run(scenario.name, func(t *testing.T) {
			root := acceptanceObserverFixture(t)
			path := filepath.Join(root, "home/.opensocrates/transactions/0123456789abcdef0123456789abcdef.json")
			original := acceptanceObserverWrite(t, path, map[string]any{"schema": lifecycle.JournalSchema, "stage": "preparing", "registration_started": false, "files": scenario.files, "id": "PRIVATE-PHASE-TEXT", "arbitrary_path": root})
			actual := acceptanceInstallFailureObservation(root)
			for key, want := range map[string]any{"file_operations_status": scenario.status, "file_operation_count": scenario.count, "planned_operation_count": scenario.planned, "prepared_operation_count": scenario.prepared, "next_planned_operation_index": scenario.next} {
				if actual[key] != want {
					t.Errorf("%s=%v want %v", key, actual[key], want)
				}
			}
			output, err := json.Marshal(actual)
			encodedRoot, _ := json.Marshal(root)
			if err != nil || bytes.Contains(output, []byte("PRIVATE-PHASE-TEXT")) || bytes.Contains(output, encodedRoot) {
				t.Fatal("operation observation leaked private content")
			}
			after, err := platform.ReadFile(path, 8<<20)
			if err != nil || !bytes.Equal(after, original) {
				t.Fatal("operation observation mutated journal")
			}
		})
	}
}

func TestAcceptanceInstallFailureObservationBoundsOperationArray(t *testing.T) {
	for _, count := range []int{64, 65} {
		t.Run(fmt.Sprintf("operations-%d", count), func(t *testing.T) {
			root := acceptanceObserverFixture(t)
			files := []any{}
			for i := 0; i < count; i++ {
				files = append(files, map[string]any{"phase": "planned", "target": "PRIVATE-PATH-NOT-EXPORTED"})
			}
			acceptanceObserverWrite(t, filepath.Join(root, "home/.opensocrates/transactions/0123456789abcdef0123456789abcdef.json"), map[string]any{"schema": lifecycle.JournalSchema, "stage": "preparing", "registration_started": false, "files": files})
			actual := acceptanceInstallFailureObservation(root)
			if count <= 64 {
				if actual["file_operations_status"] != "available" || actual["file_operation_count"] != 64 || actual["planned_operation_count"] != 64 || actual["prepared_operation_count"] != 0 || actual["next_planned_operation_index"] != 0 {
					t.Fatal("bounded complete operation inventory rejected")
				}
			} else if actual["file_operations_status"] != "unknown" || actual["file_operation_count"] != -1 || actual["planned_operation_count"] != -1 || actual["prepared_operation_count"] != -1 || actual["next_planned_operation_index"] != -1 {
				t.Fatal("over-limit operation progress inferred")
			}
			output, _ := json.Marshal(actual)
			if bytes.Contains(output, []byte("PRIVATE-PATH-NOT-EXPORTED")) {
				t.Fatal("operation path exported")
			}
		})
	}
}
