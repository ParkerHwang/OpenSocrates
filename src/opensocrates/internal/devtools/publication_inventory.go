package devtools

import (
	"archive/zip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"io"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

func publicationBundleManifest(archive string) (map[string]any, error) {
	reader, err := zip.OpenReader(archive)
	if err != nil {
		return nil, err
	}
	defer reader.Close()
	names := map[string]bool{}
	entries := map[string]*zip.File{}
	var manifest map[string]any
	for _, entry := range reader.File {
		cleaned := path.Clean(entry.Name)
		if entry.Name == "" || cleaned != strings.TrimSuffix(entry.Name, "/") || path.IsAbs(entry.Name) || strings.Contains(entry.Name, "\\") || cleaned == ".." || strings.HasPrefix(cleaned, "../") || names[cleaned] || entry.Mode()&os.ModeSymlink != 0 {
			return nil, errors.New("release_archive_path_invalid")
		}
		names[cleaned] = true
		if !entry.FileInfo().Mode().IsRegular() {
			return nil, errors.New("release_archive_nonregular")
		}
		entries[entry.Name] = entry
		if entry.Name == "bundle-manifest.json" {
			if entry.UncompressedSize64 > 4*1024*1024 {
				return nil, errors.New("release_manifest_oversize")
			}
			stream, err := entry.Open()
			if err != nil {
				return nil, err
			}
			data, err := io.ReadAll(io.LimitReader(stream, 4*1024*1024+1))
			stream.Close()
			if err != nil || len(data) > 4*1024*1024 {
				return nil, errors.New("release_manifest_invalid")
			}
			decoded, err := contracts.Decode(data)
			manifest = obj(decoded)
			if err != nil || manifest == nil {
				return nil, errors.New("release_manifest_invalid")
			}
		}
	}
	if manifest == nil {
		return nil, errors.New("release_manifest_missing")
	}
	listed := map[string]bool{"bundle-manifest.json": true}
	total := uint64(0)
	for _, item := range arr(manifest["files"]) {
		record := obj(item)
		name := str(record["path"])
		entry := entries[name]
		if name == "" || listed[name] || entry == nil || entry.UncompressedSize64 > 1024*1024*1024 {
			return nil, errors.New("release_archive_inventory_invalid")
		}
		listed[name] = true
		total += entry.UncompressedSize64
		if total > 2*1024*1024*1024 {
			return nil, errors.New("release_archive_oversize")
		}
		stream, err := entry.Open()
		if err != nil {
			return nil, err
		}
		h := sha256.New()
		size, err := io.Copy(h, io.LimitReader(stream, int64(entry.UncompressedSize64)+1))
		stream.Close()
		if err != nil || uint64(size) != entry.UncompressedSize64 || hex.EncodeToString(h.Sum(nil)) != strings.TrimPrefix(str(record["sha256"]), "sha256:") {
			return nil, errors.New("release_archive_digest_mismatch")
		}
		if expected, ok := schemaNumber(record["size"]); !ok || !expected.IsInt() || expected.Num().Int64() != size {
			return nil, errors.New("release_archive_size_mismatch")
		}
		if mode, ok := schemaNumber(record["mode"]); !ok || !mode.IsInt() || mode.Num().Int64() != int64(entry.Mode().Perm()) {
			return nil, errors.New("release_archive_mode_mismatch")
		}
	}
	if len(listed) != len(entries) {
		return nil, errors.New("release_archive_unlisted_files")
	}
	return manifest, nil
}

func publicationRequireSigning(root, target, commit string, manifest map[string]any) error {
	data, err := os.ReadFile(filepath.Join(root, "build", "evidence", "platform-signing-"+target+".json"))
	if err != nil {
		return errors.New("release_signing_evidence_missing")
	}
	var receipt map[string]any
	if json.Unmarshal(data, &receipt) != nil || receipt["schema"] != "opensocrates.platform-signing/1.0.0" || receipt["target"] != target || receipt["commit"] != commit || receipt["status"] != "verified" || receipt["native"] != true {
		return errors.New("release_signing_evidence_invalid")
	}
	indexed := map[string]map[string]any{}
	for _, item := range arr(manifest["files"]) {
		record := obj(item)
		indexed[str(record["path"])] = record
	}
	for _, item := range arr(receipt["files"]) {
		record := obj(item)
		asset := indexed["bin/"+str(record["name"])]
		if asset == nil || strings.TrimPrefix(str(asset["sha256"]), "sha256:") != str(record["sha256"]) {
			return errors.New("release_signing_manifest_mismatch")
		}
	}
	if len(arr(receipt["files"])) != 2 {
		return errors.New("release_signing_inventory_invalid")
	}
	return nil
}

func publicationMerge(o publicationOptions) error {
	commit, err := publicationIdentity(o.root)
	if err != nil {
		return err
	}
	version, err := publicationVersion(o.root)
	if err != nil {
		return err
	}
	dist := filepath.Join(o.root, "dist")
	manifests := map[string]map[string]any{}
	for _, target := range []string{"darwin-arm64", "windows-x64"} {
		archive := filepath.Join(dist, "opensocrates-v"+version+"-"+target+".zip")
		manifest, err := publicationBundleManifest(archive)
		if err != nil {
			return err
		}
		if manifest["schema"] != "opensocrates.native-bundle/1.0.0" || manifest["product_version"] != version || manifest["target"] != target || manifest["source_git_commit"] != commit || manifest["dirty_tree"] != false {
			return errors.New("release_bundle_identity_mismatch")
		}
		if err = publicationRequireSigning(o.root, target, commit, manifest); err != nil {
			return err
		}
		manifests[target] = manifest
	}
	mac, windows := manifests["darwin-arm64"], manifests["windows-x64"]
	for _, field := range []string{"source_tree_hash", "normalized_semantic_hash", "content_revision"} {
		if jsonToken(mac[field]) != jsonToken(windows[field]) {
			return errors.New("release_cross_platform_content_mismatch")
		}
	}
	for _, profile := range []string{"claude-chat", "antigravity"} {
		inventory := func(bundle map[string]any) map[string]any {
			result := map[string]any{}
			for _, entry := range arr(bundle["files"]) {
				record := obj(entry)
				name := str(record["path"])
				if strings.HasPrefix(name, "packages/"+profile+"/") {
					result[name] = record
				}
			}
			return result
		}
		macFiles, windowsFiles := inventory(mac), inventory(windows)
		if len(macFiles) == 0 || jsonToken(macFiles) != jsonToken(windowsFiles) {
			return errors.New("release_portable_export_mismatch")
		}
	}
	// Native notarization must bind the exact final macOS ZIP bytes.
	var notary map[string]any
	data, err := os.ReadFile(filepath.Join(o.root, "build", "evidence", "notarization-darwin-arm64.json"))
	if err != nil || json.Unmarshal(data, &notary) != nil || notary["status"] != "Accepted" || notary["commit"] != commit {
		return errors.New("release_notarization_evidence_missing")
	}
	hash, _, err := publicationHash(filepath.Join(dist, "opensocrates-v"+version+"-darwin-arm64.zip"))
	if err != nil || notary["sha256"] != hash {
		return errors.New("release_notarization_bytes_mismatch")
	}
	for _, target := range []string{"darwin-arm64", "windows-x64"} {
		provenance, err := ReadObject(filepath.Join(o.root, "build", "evidence", "package-source-provenance-"+target+".json"))
		if err != nil || provenance["commit"] != commit || provenance["repository"] != publicationRepository {
			return errors.New("release_native_provenance_mismatch")
		}
		sbom, err := ReadObject(filepath.Join(o.root, "build", "evidence", "sbom-"+target+".json"))
		if err != nil || sbom["bomFormat"] != "CycloneDX" {
			return errors.New("release_sbom_missing")
		}
		properties := map[string]string{}
		for _, value := range arr(obj(sbom["metadata"])["properties"]) {
			record := obj(value)
			properties[str(record["name"])] = str(record["value"])
		}
		if properties["opensocrates.source.commit"] != commit || properties["opensocrates.target"] != target {
			return errors.New("release_sbom_identity_mismatch")
		}
		if err = writeJSON(filepath.Join(dist, "opensocrates-v"+version+"-"+target+"-sbom.cdx.json"), sbom); err != nil {
			return err
		}
	}
	return writeJSON(filepath.Join(dist, "opensocrates-v"+version+"-release-manifest.json"), map[string]any{"schema": "opensocrates.native-release/1.0.0", "product_version": version, "source_git_commit": commit, "content_revision": mac["content_revision"], "source_tree_hash": mac["source_tree_hash"], "normalized_semantic_hash": mac["normalized_semantic_hash"], "bundles": manifests, "native_targets": []string{"darwin-arm64", "windows-x64"}, "account_activation": "separate user upload/activation", "running_conversations": "unchanged until host reload or fresh session"})
}

// publicationFinalize runs after online TUF metadata signing and records one
// exact publication set. It rejects directories, foreign assets and staged
// unsigned copies; the inventory is retained only as Actions evidence.
func publicationFinalize(o publicationOptions) error {
	commit, err := publicationIdentity(o.root)
	if err != nil {
		return err
	}
	version, err := publicationVersion(o.root)
	if err != nil {
		return err
	}
	names := []string{"opensocrates-v" + version + "-darwin-arm64", "opensocrates-v" + version + "-windows-x64.exe", "opensocrates-v" + version + "-darwin-arm64.zip", "opensocrates-v" + version + "-windows-x64.zip", "opensocrates-v" + version + "-release-manifest.json", "root.json", "targets.json", "snapshot.json", "timestamp.json"}
	names = append(names, "opensocrates-claude-chat-v"+version+".zip", "opensocrates-antigravity-v"+version+".zip")
	for _, target := range []string{"darwin-arm64", "windows-x64"} {
		names = append(names, "opensocrates-v"+version+"-"+target+"-sbom.cdx.json")
	}
	entries, err := os.ReadDir(filepath.Join(o.root, "dist"))
	if err != nil {
		return err
	}
	versionedRole := regexp.MustCompile(`^[1-9][0-9]*\.(root|targets|snapshot)\.json$`)
	for _, entry := range entries {
		if versionedRole.MatchString(entry.Name()) {
			names = append(names, entry.Name())
		}
	}
	// Root must be the approved embedded production trust root, not a checksum
	// next to an untrusted download. The updater signer separately verifies it.
	rootData, err := os.ReadFile(filepath.Join(o.root, "config", "update", "root.json"))
	if err != nil {
		return err
	}
	var trusted map[string]any
	if json.Unmarshal(rootData, &trusted) != nil || obj(trusted["signed"])["_type"] != "root" || len(arr(trusted["signatures"])) == 0 {
		return errors.New("release_production_root_unavailable")
	}
	staged, err := os.ReadFile(filepath.Join(o.root, "dist", "root.json"))
	if err != nil || string(staged) != string(rootData) {
		return errors.New("release_production_root_mismatch")
	}
	for _, target := range []string{"darwin-arm64", "windows-x64"} {
		file := "opensocrates-v" + version + "-" + target
		if target == "windows-x64" {
			file += ".exe"
		}
		// Verify the standalone installer is the same signed executable in the bundle.
		expected := ""
		manifest, err := publicationBundleManifest(filepath.Join(o.root, "dist", "opensocrates-v"+version+"-"+target+".zip"))
		if err != nil {
			return err
		}
		binary := "bin/opensocrates"
		if target == "windows-x64" {
			binary += ".exe"
		}
		for _, entry := range arr(manifest["files"]) {
			record := obj(entry)
			if record["path"] == binary {
				expected = strings.TrimPrefix(str(record["sha256"]), "sha256:")
			}
		}
		actual, _, err := publicationHash(filepath.Join(o.root, "dist", file))
		if err != nil || actual != expected {
			return errors.New("release_installer_bundle_mismatch")
		}
	}
	sort.Strings(names)
	inventory := publicationInventory{Schema: "opensocrates.publication-inventory/1.0.0", ProductVersion: version, Commit: commit, Assets: []publicationAsset{}}
	checksums := ""
	for _, name := range names {
		hash, size, err := publicationHash(filepath.Join(o.root, "dist", name))
		if err != nil {
			return err
		}
		inventory.Assets = append(inventory.Assets, publicationAsset{Name: name, Size: size, SHA256: hash})
		checksums += hash + "  " + name + "\n"
	}
	checksumName := "opensocrates-v" + version + "-checksums.sha256"
	if err = writeData(filepath.Join(o.root, "dist", checksumName), []byte(checksums), 0644); err != nil {
		return err
	}
	hash, size, err := publicationHash(filepath.Join(o.root, "dist", checksumName))
	if err != nil {
		return err
	}
	inventory.Assets = append(inventory.Assets, publicationAsset{Name: checksumName, Size: size, SHA256: hash})
	return writeJSON(filepath.Join(o.root, "dist", "opensocrates-v"+version+"-publication-inventory.json"), inventory)
}
