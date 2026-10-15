package devtools

import (
	"archive/zip"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func notarizationInventoryFixture(t *testing.T) (string, map[string]any) {
	t.Helper()
	root := t.TempDir()
	dist := filepath.Join(root, "dist")
	os.MkdirAll(dist, 0700)
	archive := "opensocrates-v1.6.0-darwin-arm64.zip"
	installer := "opensocrates-v1.6.0-darwin-arm64"
	data := []byte("signed candidate runtime")
	paths := []string{"bin/opensocrates", "bin/opensocrates-update-helper", "packages/codex/runtime/darwin-arm64/opensocrates", "packages/claude/runtime/darwin-arm64/opensocrates"}
	output, err := os.Create(filepath.Join(dist, archive))
	if err != nil {
		t.Fatal(err)
	}
	writer := zip.NewWriter(output)
	entries := []any{}
	files := []any{}
	for _, name := range paths {
		header := &zip.FileHeader{Name: name, Method: zip.Store}
		header.SetMode(0755)
		entry, err := writer.CreateHeader(header)
		if err != nil {
			t.Fatal(err)
		}
		entry.Write(data)
		hash := strings.TrimPrefix(digest(data), "sha256:")
		entries = append(entries, map[string]any{"path": name, "sha256": hash, "size": len(data), "mode": 493})
		files = append(files, map[string]any{"path": name, "sha256": hash, "size": len(data), "cdhash": strings.Repeat("b", 40)})
	}
	encoded, _ := json.Marshal(map[string]any{"files": entries})
	entry, _ := writer.Create("bundle-manifest.json")
	entry.Write(encoded)
	writer.Close()
	output.Close()
	os.WriteFile(filepath.Join(dist, installer), data, 0755)
	hash, size, _ := publicationHash(filepath.Join(dist, archive))
	installerHash, installerSize, _ := publicationHash(filepath.Join(dist, installer))
	log := func(tickets int) map[string]any {
		return map[string]any{"status": "Accepted", "sha256_matches": true, "issue_count": 0, "ticket_count": tickets, "all_runtime_cdhashes_ticketed": true}
	}
	payloadID := "00000000-0000-0000-0000-000000000001"
	receipt := map[string]any{"schema": "opensocrates.notarization/1.0.0", "commit": strings.Repeat("a", 40), "status": "Accepted", "submission_id": payloadID, "archive": archive, "sha256": hash, "size": size, "apple_log": log(4), "runtime_files": files,
		"standalone_installer": map[string]any{"status": "Accepted", "submission_id": "00000000-0000-0000-0000-000000000002", "archive": "installer-notary.zip", "sha256": strings.Repeat("c", 64), "size": 42, "apple_log": log(1), "payload_submission_id": payloadID, "payload_notarized_first": true, "installer": installer, "installer_sha256": installerHash, "installer_size": installerSize, "runtime_files": []any{map[string]any{"path": installer, "sha256": installerHash, "size": installerSize, "cdhash": strings.Repeat("b", 40)}}},
	}
	return root, receipt
}
func TestPublicationRequiresSeparateInstallerNotarizationBoundToFinalBytes(t *testing.T) {
	for _, test := range []struct {
		name   string
		change func(map[string]any)
	}{
		{"valid", func(map[string]any) {}},
		{"candidate_schema", func(r map[string]any) { r["schema"] = "opensocrates.macos-notarization-candidate/2.0.0" }},
		{"missing_installer", func(r map[string]any) { delete(r, "standalone_installer") }},
		{"rejected_installer", func(r map[string]any) { obj(r["standalone_installer"])["status"] = "Rejected" }},
		{"reused_payload_id", func(r map[string]any) { obj(r["standalone_installer"])["submission_id"] = r["submission_id"] }},
		{"foreign_payload_binding", func(r map[string]any) {
			obj(r["standalone_installer"])["payload_submission_id"] = "00000000-0000-0000-0000-000000000003"
		}},
		{"wrong_installer_hash", func(r map[string]any) { obj(r["standalone_installer"])["installer_sha256"] = strings.Repeat("d", 64) }},
		{"wrong_installer_cdhash", func(r map[string]any) {
			obj(arr(obj(r["standalone_installer"])["runtime_files"])[0])["cdhash"] = strings.Repeat("d", 40)
		}},
		{"payload_warning", func(r map[string]any) { obj(r["apple_log"])["issue_count"] = 1 }},
		{"missing_ticket", func(r map[string]any) { obj(r["apple_log"])["ticket_count"] = 3 }},
		{"duplicate_runtime", func(r map[string]any) { arr(r["runtime_files"])[3] = arr(r["runtime_files"])[0] }},
	} {
		t.Run(test.name, func(t *testing.T) {
			root, receipt := notarizationInventoryFixture(t)
			test.change(receipt)
			if err := publicationReceipt(root, "notarization-darwin-arm64.json", receipt); err != nil {
				t.Fatal(err)
			}
			err := publicationRequireNotarization(root, "1.6.0", strings.Repeat("a", 40))
			if (err != nil) != (test.name != "valid") {
				t.Fatalf("receipt binding result: %v", err)
			}
		})
	}
}
func TestPublicationRejectsInstallerModifiedAfterAppleAcceptance(t *testing.T) {
	root, receipt := notarizationInventoryFixture(t)
	publicationReceipt(root, "notarization-darwin-arm64.json", receipt)
	os.WriteFile(filepath.Join(root, "dist", "opensocrates-v1.6.0-darwin-arm64"), []byte("modified installer"), 0755)
	if err := publicationRequireNotarization(root, "1.6.0", strings.Repeat("a", 40)); err == nil {
		t.Fatal("modified standalone installer published")
	}
}
