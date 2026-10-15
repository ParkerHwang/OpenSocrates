//go:build windows

package lifecycle

import (
	"path/filepath"
	"testing"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"golang.org/x/sys/windows"
)

func TestInspectRejectsNestedWindowsBroadWritableDACL(t *testing.T) {
	root := privateLifecycleTestDir(t)
	nested := filepath.Join(root, "nested")
	if err := platform.Mkdir(nested); err != nil {
		t.Fatal(err)
	}
	leaf := filepath.Join(nested, "leaf.bin")
	if err := platform.AtomicWrite(leaf, []byte("synthetic owned bytes"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := Inspect(root); err != nil {
		t.Fatal("private nested fixture was rejected")
	}
	sd, err := windows.SecurityDescriptorFromString("D:P(A;;FA;;;WD)")
	if err != nil {
		t.Fatal(err)
	}
	acl, _, err := sd.DACL()
	if err != nil {
		t.Fatal(err)
	}
	if err := windows.SetNamedSecurityInfo(leaf, windows.SE_FILE_OBJECT, windows.DACL_SECURITY_INFORMATION|windows.PROTECTED_DACL_SECURITY_INFORMATION, nil, nil, acl, nil); err != nil {
		t.Fatal(err)
	}
	if err := platform.GuardOwned(root); err != nil {
		t.Fatal("root itself should remain owned")
	}
	if digest, err := platform.SHA256File(leaf, MaxFileBytes); err == nil || digest != "" || diagnostics.CodeOf(err) != diagnostics.Permission {
		t.Fatal("owned-handle hasher accepted a broad writable leaf DACL")
	}
	if _, err := Inspect(root); err == nil || diagnostics.CodeOf(err) != diagnostics.Permission {
		t.Fatal("tree inventory accepted a broad writable nested leaf DACL")
	}
}
