package management

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strconv"
	"testing"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/lifecycle"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/registration"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
)

func purgeFixtureDir(t *testing.T) string {
	t.Helper()
	root := filepath.Join(t.TempDir(), "private")
	if e := platform.Mkdir(root); e != nil {
		t.Fatal(e)
	}
	return root
}
func purgeFixtureWrite(t *testing.T, p string, b []byte) {
	t.Helper()
	if e := platform.Mkdir(filepath.Dir(p)); e != nil {
		t.Fatal(e)
	}
	if e := platform.AtomicWrite(p, b, 0600); e != nil {
		t.Fatal(e)
	}
}
func purgeCacheFixture(t *testing.T, root, version string) {
	t.Helper()
	release, _ := json.Marshal(map[string]any{"schema": "opensocrates.plugin-release-manifest/1.0.0", "host": "codex", "product_version": version, "content_revision": 3})
	plugin, _ := json.Marshal(map[string]string{"name": "opensocrates", "version": version})
	payload := map[string][]byte{"release-manifest.json": release, ".codex-plugin/plugin.json": plugin, "content/한글.md": []byte("preserved released content")}
	var checks bytes.Buffer
	for _, name := range sortedKeys(payload) {
		purgeFixtureWrite(t, filepath.Join(root, filepath.FromSlash(name)), payload[name])
		h := sha256.Sum256(payload[name])
		checks.WriteString(hex.EncodeToString(h[:]) + "  " + name + "\n")
	}
	purgeFixtureWrite(t, filepath.Join(root, "checksums.sha256"), checks.Bytes())
}
func TestPurgeCacheRejectsModifiedUnknownAndLinkedFiles(t *testing.T) {
	for _, kind := range []string{"modified", "unknown", "linked", "bad-revision"} {
		t.Run(kind, func(t *testing.T) {
			root := filepath.Join(purgeFixtureDir(t), "1.5.0")
			purgeCacheFixture(t, root, "1.5.0")
			switch kind {
			case "modified":
				purgeFixtureWrite(t, filepath.Join(root, "content/한글.md"), []byte("changed"))
			case "unknown":
				purgeFixtureWrite(t, filepath.Join(root, "unknown"), []byte("foreign"))
			case "linked":
				original := filepath.Join(root, "content/한글.md")
				if e := os.Link(original, filepath.Join(root, "linked")); e != nil {
					t.Skip("hard links unavailable")
				}
			case "bad-revision":
				purgeFixtureWrite(t, filepath.Join(root, "release-manifest.json"), []byte(`{"schema":"opensocrates.plugin-release-manifest/1.0.0","host":"codex","product_version":"1.5.0","content_revision":null}`))
			}
			if _, e := verifyPurgePackage(root, "1.5.0"); e == nil {
				t.Fatal("unsafe payload accepted")
			}
			if _, e := os.Lstat(root); e != nil {
				t.Fatal("inspection deleted original")
			}
		})
	}
}
func TestPurgeCacheDefersLiveOwnedPID(t *testing.T) {
	root := purgeFixtureDir(t)
	base := filepath.Join(root, "codex")
	market := filepath.Join(base, "plugins", "cache", "opensocrates")
	live := filepath.Join(market, "opensocrates", "1.5.0")
	old := filepath.Join(market, "opensocrates", "1.4.0")
	purgeCacheFixture(t, live, "1.5.0")
	purgeCacheFixture(t, old, "1.4.0")
	purgeFixtureWrite(t, filepath.Join(live, ".in_use", strconv.Itoa(os.Getpid())), nil)
	m := &Manager{}
	plan := lifecycle.Plan{}
	pending, e := m.prepareCachePurge(Paths{Base: base}, &plan)
	if e != nil || !pending || len(plan.Mutations) != 1 || plan.Mutations[0].Target != old {
		t.Fatalf("live cache not deferred: %v", e)
	}
	if _, e := os.Stat(live); e != nil {
		t.Fatal("live cache deleted")
	}
}
func TestPurgeCacheExactEmptyMarketplaceAndForeignSibling(t *testing.T) {
	root := purgeFixtureDir(t)
	base := filepath.Join(root, "codex")
	market := filepath.Join(base, "plugins/cache/opensocrates")
	if e := platform.Mkdir(market); e != nil {
		t.Fatal(e)
	}
	m := &Manager{}
	plan := lifecycle.Plan{}
	pending, e := m.prepareCachePurge(Paths{Base: base}, &plan)
	if e != nil || pending || len(plan.Mutations) != 1 || plan.Mutations[0].Target != market {
		t.Fatal("empty exact marketplace not planned")
	}
	purgeFixtureWrite(t, filepath.Join(market, "foreign"), []byte("untouched"))
	plan = lifecycle.Plan{}
	if _, e := m.prepareCachePurge(Paths{Base: base}, &plan); e == nil {
		t.Fatal("foreign sibling accepted")
	}
}

type purgeFakeAdapter struct {
	state registration.State
	fail  bool
}

func (a *purgeFakeAdapter) Inspect(context.Context, string) (registration.State, error) {
	return a.state, nil
}
func (a *purgeFakeAdapter) Verify(_ context.Context, s registration.State) error {
	if !reflect.DeepEqual(a.state, s) {
		return trustFailure()
	}
	return nil
}
func (a *purgeFakeAdapter) Replace(_ context.Context, before, after registration.State) error {
	if a.fail {
		return trustFailure()
	}
	a.state = after
	return nil
}

func TestPurgeTransactionKeepsHistoryAndUnknownState(t *testing.T) {
	root := purgeFixtureDir(t)
	home := filepath.Join(root, "home")
	state := filepath.Join(root, "state")
	base := filepath.Join(home, ".codex")
	if e := platform.Mkdir(home); e != nil {
		t.Fatal(e)
	}
	cache := filepath.Join(base, "plugins/cache/opensocrates/opensocrates/1.5.0")
	purgeCacheFixture(t, cache, "1.5.0")
	purgeFixtureWrite(t, filepath.Join(base, "config.toml"), []byte("# preserve trust\n[hooks.state.\""+codexTrustPrefix+"stop:0:0\"]\ntrusted_hash = \"same\"\n"))
	purgeFixtureWrite(t, filepath.Join(base, "sessions/history.json"), []byte(`{"private":"conversation"}`))
	purgeFixtureWrite(t, filepath.Join(state, "unknown-state.json"), []byte(`{"future":9007199254740993}`))
	adapter := &purgeFakeAdapter{state: registration.State{Root: filepath.Join(base, "managed-marketplaces/opensocrates")}}
	scheduler := update.NewSchedulerAdapter("darwin", home, filepath.Join(state, "bin/opensocrates"), state)
	m := &Manager{Home: home, StateDir: state, GOOS: "darwin", GOARCH: "arm64", Scheduler: scheduler, Engine: &lifecycle.Engine{StateDir: state, Registrations: map[string]registration.Adapter{"codex": adapter}}, LookupEnv: func(key string) string {
		if key == "CODEX_HOME" {
			return base
		}
		return ""
	}}
	r, e := m.Handle(context.Background(), Request{Action: "remove", Host: "codex", Purge: true})
	if e != nil {
		t.Fatal(e)
	}
	if r.Purge.Status != "complete" || r.Integrity != "verified" {
		t.Fatal("purge completion not verified")
	}
	if _, e := os.Lstat(cache); !os.IsNotExist(e) {
		t.Fatal("owned cache payload retained")
	}
	for _, p := range []string{filepath.Join(base, "config.toml"), filepath.Join(base, "sessions/history.json"), filepath.Join(state, "unknown-state.json")} {
		if _, e := os.Stat(p); e != nil {
			t.Fatal("unowned user state removed")
		}
	}
	pending, e := m.Engine.Pending()
	if e != nil || len(pending) != 0 {
		t.Fatal("cleanup left pending transaction")
	}
}

func TestPurgeLegacyFinalizationOnlyKnownSchema(t *testing.T) {
	root := purgeFixtureDir(t)
	m := &Manager{StateDir: root}
	known := filepath.Join(root, "auto-update-receipt.json")
	foreign := filepath.Join(root, "custom.json")
	purgeFixtureWrite(t, known, []byte(`{"schema":"opensocrates.auto-update-receipt/1.1.0","result":"same"}`))
	purgeFixtureWrite(t, foreign, []byte(`{"private":"keep"}`))
	plan := lifecycle.Plan{}
	if e := m.prepareLegacyStatePurge(&plan); e != nil || len(plan.Mutations) != 1 || plan.Mutations[0].Target != known {
		t.Fatalf("precise finalization: %v", e)
	}
	purgeFixtureWrite(t, known, []byte(`{"schema":"foreign.owner/1.0.0","private":"keep"}`))
	plan = lifecycle.Plan{}
	if e := m.prepareLegacyStatePurge(&plan); e == nil {
		t.Fatal("foreign replacement treated as owned")
	}
	if _, e := os.Stat(foreign); e != nil {
		t.Fatal("foreign state lost")
	}
}

func purgeTrustManager(t *testing.T) (*Manager, string, string) {
	t.Helper()
	root := purgeFixtureDir(t)
	home := filepath.Join(root, "home")
	state := filepath.Join(root, "state")
	base := filepath.Join(home, ".codex")
	if e := platform.Mkdir(home); e != nil {
		t.Fatal(e)
	}
	config := filepath.Join(base, "config.toml")
	purgeFixtureWrite(t, config, []byte("# user settings 한글\nmodel = \"same\"\n[hooks.state.\""+codexTrustPrefix+"stop:0:0\"] # owned\ntrusted_hash = \"new-or-old-hash\" # owned\n"))
	cache := filepath.Join(base, "plugins/cache/opensocrates/opensocrates/1.5.0")
	purgeCacheFixture(t, cache, "1.5.0")
	adapter := &purgeFakeAdapter{state: registration.State{Root: filepath.Join(base, "managed-marketplaces/opensocrates")}}
	m := &Manager{Home: home, StateDir: state, GOOS: "darwin", GOARCH: "arm64", Scheduler: update.NewSchedulerAdapter("darwin", home, filepath.Join(state, "bin/opensocrates"), state), Engine: &lifecycle.Engine{StateDir: state, Registrations: map[string]registration.Adapter{"codex": adapter}}, LookupEnv: func(key string) string {
		if key == "CODEX_HOME" {
			return base
		}
		if key == "CODEX_BIN" {
			return "synthetic-codex"
		}
		return ""
	}}
	return m, config, cache
}
func TestPurgeResetTrustValidatesOriginalAndCandidateOnlyOnExplicitRequest(t *testing.T) {
	m, config, _ := purgeTrustManager(t)
	original, e := platform.ReadOwnedFile(config, maxCodexConfigBytes)
	if e != nil {
		t.Fatal(e)
	}
	reset, e := StripCodexTrust(original)
	if e != nil {
		t.Fatal(e)
	}
	var validated [][]byte
	m.TrustConfigValidator = func(_ context.Context, binary string, b []byte) error {
		if binary != "synthetic-codex" {
			t.Fatal("wrong host executable")
		}
		validated = append(validated, append([]byte{}, b...))
		return nil
	}
	result, e := m.Handle(context.Background(), Request{Action: "remove", Host: "codex", Purge: true, ResetTrust: true})
	if e != nil {
		t.Fatal(e)
	}
	if len(validated) != 2 || !bytes.Equal(validated[0], original) || !bytes.Equal(validated[1], reset.Contents) {
		t.Fatal("isolated validation did not see exact original and candidate")
	}
	actual, e := platform.ReadOwnedFile(config, maxCodexConfigBytes)
	if e != nil || !bytes.Equal(actual, reset.Contents) {
		t.Fatal("verified candidate not activated")
	}
	if result.Purge.TrustTransaction == "" || result.Purge.Status != "complete" {
		t.Fatal("trust journal not reported")
	}
}
func TestPurgeTrustValidationFailurePreservesPayloadAndConfiguration(t *testing.T) {
	m, config, cache := purgeTrustManager(t)
	original, _ := platform.ReadOwnedFile(config, maxCodexConfigBytes)
	m.TrustConfigValidator = func(context.Context, string, []byte) error { return trustFailure() }
	result, e := m.Handle(context.Background(), Request{Action: "remove", Host: "codex", Purge: true, ResetTrust: true})
	if e == nil || result.Purge.Status != "partial" {
		t.Fatal("failed validator allowed purge")
	}
	actual, e := platform.ReadOwnedFile(config, maxCodexConfigBytes)
	if e != nil || !bytes.Equal(actual, original) {
		t.Fatal("configuration changed after validator failure")
	}
	if _, e := os.Stat(cache); e != nil {
		t.Fatal("payload removed after validator failure")
	}
}
func TestPurgeLaterFailurePreservesVerifiedExplicitReset(t *testing.T) {
	m, config, cache := purgeTrustManager(t)
	original, _ := platform.ReadOwnedFile(config, maxCodexConfigBytes)
	reset, _ := StripCodexTrust(original)
	m.TrustConfigValidator = func(context.Context, string, []byte) error { return nil }
	purgeFixtureWrite(t, filepath.Join(cache, "unknown-user-file"), []byte("foreign bytes"))
	result, e := m.Handle(context.Background(), Request{Action: "remove", Host: "codex", Purge: true, ResetTrust: true})
	if e == nil || result.Purge.TrustTransaction == "" {
		t.Fatal("foreign cache accepted or reset journal missing")
	}
	actual, e := platform.ReadOwnedFile(config, maxCodexConfigBytes)
	if e != nil || !bytes.Equal(actual, reset.Contents) {
		t.Fatal("later payload failure undid explicitly committed reset")
	}
	if _, e := os.Stat(filepath.Join(cache, "unknown-user-file")); e != nil {
		t.Fatal("foreign cache file removed")
	}
}

func TestAbsentTrustStillValidatesOriginalAndDetectsConcurrentEdit(t *testing.T) {
	for _, change := range []bool{false, true} {
		t.Run(strconv.FormatBool(change), func(t *testing.T) {
			m, config, _ := purgeTrustManager(t)
			original := []byte("# unchanged settings\nmodel = \"same\"\n")
			purgeFixtureWrite(t, config, original)
			calls := 0
			m.TrustConfigValidator = func(_ context.Context, _ string, b []byte) error {
				calls++
				if !bytes.Equal(b, original) {
					t.Fatal("original validation bytes changed")
				}
				if change {
					purgeFixtureWrite(t, config, []byte("model = \"user-changed\"\n"))
				}
				return nil
			}
			plan := lifecycle.Plan{}
			p := Paths{Base: filepath.Dir(config)}
			reset, e := m.prepareTrustReset(context.Background(), p, filepath.Dir(config), &plan)
			if calls != 1 {
				t.Fatal("absent trust bypassed installed host validation")
			}
			if change {
				if e == nil {
					t.Fatal("concurrent config edit accepted")
				}
			} else if e != nil || len(reset.RemovedEvents) != 0 || len(plan.Mutations) != 0 {
				t.Fatal("absent trust attempted mutation")
			}
		})
	}
}
