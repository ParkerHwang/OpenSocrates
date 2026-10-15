package devtools

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Keychain lifecycle fixtures exercise Darwin absolute search-list paths and
// private POSIX file modes. Portable identity, bounds, environment and native
// host rejection coverage remains in macos_signing_keychain_test.go.
type macSigningFake struct {
	t                 *testing.T
	list              []string
	identities, certs []byte
	fail              string
	calls             []string
}

func (f *macSigningFake) run(root, name string, args ...string) ([]byte, error) {
	f.t.Helper()
	f.calls = append(f.calls, name+":"+args[0])
	if args[0] == f.fail {
		return nil, errors.New("mac_signing_private_command_failed")
	}
	switch args[0] {
	case "list-keychains":
		if len(args) > 3 {
			f.list = append([]string{}, args[4:]...)
			return nil, nil
		}
		rows := []string{}
		for _, path := range f.list {
			rows = append(rows, "\""+path+"\"")
		}
		return []byte(strings.Join(rows, "\n")), nil
	case "create-keychain":
		path := args[len(args)-1]
		if err := os.WriteFile(path, []byte("encrypted fixture keychain"), 0600); err != nil {
			f.t.Fatal(err)
		}
		f.list = append([]string{path}, f.list...)
	case "delete-keychain":
		return nil, os.Remove(args[1])
	case "find-identity":
		return f.identities, nil
	case "find-certificate":
		return f.certs, nil
	}
	return nil, nil
}

func TestMacSigningPrepareAndCleanupPreserveExistingKeychains(t *testing.T) {
	temp, _, ids, certs := macSigningFixture(t)
	root := filepath.Join(temp, "source")
	os.Mkdir(root, 0700)
	original := []string{"/Users/runner/Library/Keychains/login.keychain-db", "/Library/Keychains/System.keychain"}
	fake := &macSigningFake{t: t, list: append([]string{}, original...), identities: ids, certs: certs}
	if err := macSigningPrepare(root, fake.run); err != nil {
		t.Fatal(err)
	}
	path, err := macSigningOwnedKeychain()
	if err != nil {
		t.Fatal(err)
	}
	if len(fake.list) != 3 || fake.list[0] != path {
		t.Fatal("private keychain not explicitly searched")
	}
	state, err := os.ReadFile(os.Getenv("OPENSOCRATES_MAC_SIGNING_STATE"))
	if err != nil {
		t.Fatal(err)
	}
	for _, secret := range []string{"fixture-secret-app-password", "fixture-secret-p12-password", "fixture-private-p12"} {
		if strings.Contains(string(state), secret) {
			t.Fatal("private state retained credentials")
		}
	}
	if _, err = os.Stat(filepath.Join(filepath.Dir(path), "certificate.p12")); !os.IsNotExist(err) {
		t.Fatal("P12 remained after import")
	}
	if err = macSigningCleanup(root, fake.run); err != nil {
		t.Fatal(err)
	}
	if !macSigningSameList(fake.list, original) {
		t.Fatal("original search list not restored")
	}
	if _, err = os.Stat(filepath.Dir(path)); !os.IsNotExist(err) {
		t.Fatal("private directory remained")
	}
	if err = macSigningCleanup(root, fake.run); err != nil {
		t.Fatal("repeat cleanup failed")
	}
	receipt, err := os.ReadFile(filepath.Join(root, "build/evidence/macos-keychain-cleanup.json"))
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(receipt), temp) || strings.Contains(string(receipt), "fixture-secret") {
		t.Fatal("cleanup receipt leaked private metadata")
	}
}

func TestMacSigningPartialFailuresRollbackAndDoNotLogSecrets(t *testing.T) {
	for _, stage := range []string{"create-keychain", "import", "set-key-partition-list", "find-identity", "notarytool"} {
		t.Run(stage, func(t *testing.T) {
			temp, _, ids, certs := macSigningFixture(t)
			fake := &macSigningFake{t: t, list: []string{"/original.keychain-db"}, identities: ids, certs: certs, fail: stage}
			err := macSigningPrepare(temp, fake.run)
			if err == nil || strings.Contains(err.Error(), "fixture") || strings.Contains(err.Error(), temp) {
				t.Fatalf("unsafe failure: %v", err)
			}
			if !macSigningSameList(fake.list, []string{"/original.keychain-db"}) {
				t.Fatal("failed setup altered existing search list")
			}
			if _, err = os.Stat(filepath.Dir(os.Getenv("OPENSOCRATES_MAC_SIGNING_STATE"))); !os.IsNotExist(err) {
				t.Fatal("failed setup retained private material")
			}
		})
	}
}

func TestMacSigningCleanupPreservesForeignSearchListChanges(t *testing.T) {
	temp, _, ids, certs := macSigningFixture(t)
	fake := &macSigningFake{t: t, list: []string{"/original.keychain-db"}, identities: ids, certs: certs}
	if err := macSigningPrepare(temp, fake.run); err != nil {
		t.Fatal(err)
	}
	directory := filepath.Dir(os.Getenv("OPENSOCRATES_MAC_SIGNING_STATE"))
	fake.list = append(fake.list, "/foreign.keychain-db")
	err := macSigningCleanup(temp, fake.run)
	if err == nil || err.Error() != "mac_signing_cleanup_foreign_search_list_preserved" {
		t.Fatal("foreign changes not reported")
	}
	if !macSigningSameList(fake.list, []string{"/original.keychain-db", "/foreign.keychain-db"}) {
		t.Fatal("foreign keychain changed")
	}
	if _, err = os.Stat(directory); !os.IsNotExist(err) {
		t.Fatal("foreign search change retained credentials")
	}
}

func TestMacSigningCleanupRejectsForeignStateAndPartialKeychainCannotSign(t *testing.T) {
	temp, _, ids, certs := macSigningFixture(t)
	fake := &macSigningFake{t: t, list: []string{"/original.keychain-db"}, identities: ids, certs: certs}
	if err := macSigningPrepare(temp, fake.run); err != nil {
		t.Fatal(err)
	}
	statePath := os.Getenv("OPENSOCRATES_MAC_SIGNING_STATE")
	data, _ := os.ReadFile(statePath)
	var state macSigningState
	json.Unmarshal(data, &state)
	state.Prepared = false
	changed, _ := json.Marshal(state)
	os.WriteFile(statePath, changed, 0600)
	if _, err := macSigningOwnedKeychain(); err == nil {
		t.Fatal("partial preparation accepted")
	}
	state.RunID = "999"
	changed, _ = json.Marshal(state)
	os.WriteFile(statePath, changed, 0600)
	before := len(fake.calls)
	if err := macSigningCleanup(temp, fake.run); err == nil || len(fake.calls) != before {
		t.Fatal("foreign marker authorized cleanup")
	}
	os.WriteFile(statePath, data, 0600)
	if err := macSigningCleanup(temp, fake.run); err != nil {
		t.Fatal(err)
	}
}

func TestMacSigningCleanupStillDeletesPrivateFilesWhenSearchInspectionFails(t *testing.T) {
	temp, _, ids, certs := macSigningFixture(t)
	fake := &macSigningFake{t: t, list: []string{"/original.keychain-db"}, identities: ids, certs: certs}
	if err := macSigningPrepare(temp, fake.run); err != nil {
		t.Fatal(err)
	}
	directory := filepath.Dir(os.Getenv("OPENSOCRATES_MAC_SIGNING_STATE"))
	fake.fail = "list-keychains"
	for _, name := range []string{"GITHUB_REF", "GITHUB_SHA", "OPENSOCRATES_NOTARY_APP_PASSWORD", "OPENSOCRATES_MAC_CERTIFICATE_PASSWORD", "OPENSOCRATES_MAC_CERTIFICATE_P12_BASE64", "OPENSOCRATES_MAC_SIGNING_KEYCHAIN"} {
		t.Setenv(name, "")
	}
	err := macSigningCleanup(temp, fake.run)
	if err == nil || err.Error() != "mac_signing_cleanup_search_list_failed" {
		t.Fatal("search-list failure hidden")
	}
	if _, err = os.Stat(directory); !os.IsNotExist(err) {
		t.Fatal("cancelled job retained credentials")
	}
}
