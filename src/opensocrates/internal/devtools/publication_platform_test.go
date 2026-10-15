package devtools

import (
	"reflect"
	"testing"
)

func TestPublicationNativeQualificationSeparatesWindowsArchitectures(t *testing.T) {
	for _, test := range []struct {
		target, os, arch string
		native           bool
	}{
		{"darwin-arm64", "darwin", "arm64", true},
		{"windows-x64", "windows", "amd64", true},
		{"windows-arm64", "windows", "arm64", true},
		{"windows-arm64", "windows", "amd64", false},
		{"windows-x64", "windows", "arm64", false},
		{"windows-arm64", "darwin", "arm64", false},
		{"linux-arm64", "linux", "arm64", false},
	} {
		if err := publicationNativeTargetFor(test.target, test.os, test.arch); (err == nil) != test.native {
			t.Errorf("qualification %s on %s/%s=%v", test.target, test.os, test.arch, err)
		}
	}
}

func TestPublicationInventoryRetainsAllThreeNativeTargets(t *testing.T) {
	expected := []string{"darwin-arm64", "windows-x64", "windows-arm64"}
	if !reflect.DeepEqual(publicationNativeTargets(), expected) {
		t.Fatal("native release targets changed")
	}
	for _, target := range expected {
		want := "opensocrates-v1.6.0-" + target
		if target != "darwin-arm64" {
			want += ".exe"
		}
		if got := publicationInstallerName("1.6.0", target); got != want {
			t.Errorf("installer %s=%s", target, got)
		}
	}
	// Return fresh lists so no caller can silently remove another architecture
	// from the subsequent signed publication inventory.
	mutated := publicationNativeTargets()
	mutated[2] = "windows-x64"
	if !reflect.DeepEqual(publicationNativeTargets(), expected) {
		t.Fatal("caller mutated global release qualification")
	}
}
