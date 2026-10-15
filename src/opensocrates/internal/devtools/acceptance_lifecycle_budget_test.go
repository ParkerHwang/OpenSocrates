package devtools

import (
	"testing"
	"time"
)

func TestNativeLifecycleBudgetExtensionIsLimitedToBundleMutations(t *testing.T) {
	for _, name := range []string{"native_install", "offline_update_same_bundle"} {
		if nativeLifecycleCommandBudget(name) != 60*time.Second {
			t.Fatalf("full-bundle command %s lost its finite installation window", name)
		}
	}
	for _, name := range []string{"native_status", "native_diagnose", "owned_remove", "recover", "hook", "selector", "unknown", ""} {
		if nativeLifecycleCommandBudget(name) != 30*time.Second {
			t.Fatalf("unrelated command %s inherited the installation extension", name)
		}
	}
}
