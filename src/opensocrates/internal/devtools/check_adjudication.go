package devtools

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
)

var blindedPacketForbidden = map[string]bool{"selected": true, "selected_reasoning_systems": true, "intervene": true, "instructions": true, "score": true, "pass": true, "passed": true, "failure": true, "failed": true, "effort": true, "reasoning_effort": true, "aggregate": true, "recall": true, "output": true, "model_output": true, "run_id": true, "status": true, "usage": true, "latency_ms": true}

func forbiddenPacketFields(v any, path string) []string {
	codes := []string{}
	switch x := v.(type) {
	case map[string]any:
		for k, c := range x {
			if blindedPacketForbidden[k] {
				codes = append(codes, path+"."+k)
			}
			codes = append(codes, forbiddenPacketFields(c, path+"."+k)...)
		}
	case []any:
		for i, c := range x {
			codes = append(codes, forbiddenPacketFields(c, fmt.Sprintf("%s[%d]", path, i))...)
		}
	}
	return codes
}
func checkMaintainerAdjudication(root string) ([]string, error) {
	manifest, e := checkObject(filepath.Join(root, "evals/v1.2/adjudication-manifest-v1.0.0.json"))
	if e != nil {
		return nil, e
	}
	maintainer := obj(manifest["maintainer_evidence"])
	codes := []string{}
	required := map[string]string{"evals/v1.2/adjudication-queue.jsonl": str(maintainer["queue_sha256"])}
	reviewNames := map[string]string{"primary": "askpro-blind-adjudication.json", "secondary": "askpro-second-blind-adjudication.json", "claude_partial": "claude-opus5-blind-review.json", "comparison": "reviewer-comparison.json"}
	for label, name := range reviewNames {
		required["build/adjudication/v1.2/"+name] = str(obj(maintainer["review_artifact_sha256"])[label])
	}
	for name, expected := range obj(maintainer["preserved_raw_result_sha256"]) {
		required["build/evidence/v1.2/"+name] = str(expected)
	}
	for rel, expected := range required {
		p, e := safeCheckPath(root, rel)
		if e != nil {
			return codes, e
		}
		b, e := os.ReadFile(p)
		if e != nil {
			return append(codes, "private_historical_evidence_unavailable"), e
		}
		sum := sha256.Sum256(b)
		if len(expected) != 64 || hex.EncodeToString(sum[:]) != expected {
			codes = append(codes, "private_historical_evidence_hash_mismatch:"+rel)
		}
	}
	packetRoot := filepath.Join(root, "build/adjudication/v1.2/blind-packets")
	packetManifest, e := checkObject(filepath.Join(packetRoot, "packet-manifest.json"))
	if e != nil {
		return append(codes, "private_packet_manifest_unavailable"), e
	}
	packetHashes := map[string]any{}
	paths, e := filepath.Glob(filepath.Join(packetRoot, "*.json"))
	if e != nil {
		return codes, e
	}
	count := 0
	for _, p := range paths {
		if filepath.Base(p) == "packet-manifest.json" {
			continue
		}
		count++
		packet, e := checkObject(p)
		if e != nil {
			return codes, e
		}
		id := str(packet["pair_id"])
		if id == "" || id+".json" != filepath.Base(p) {
			codes = append(codes, "blind_packet_pair_id_mismatch")
		}
		if _, exists := packetHashes[id]; exists {
			codes = append(codes, "blind_packet_pair_duplicate")
		}
		body := clone(packet)
		delete(body, "decision_form")
		if len(forbiddenPacketFields(body, "$")) > 0 {
			codes = append(codes, "blind_packet_outcome_leak")
		}
		if !emptyBlindDecisionForm(packet["decision_form"], "$") {
			codes = append(codes, "blind_packet_prefilled_form")
		}
		b, e := Canonical(packet)
		if e != nil {
			return codes, e
		}
		sum := sha256.Sum256(b)
		packetHashes[id] = hex.EncodeToString(sum[:])
	}
	if count != 51 {
		codes = append(codes, "blind_packet_count_invalid")
	}
	hashes, e := Canonical(packetHashes)
	if e != nil {
		return codes, e
	}
	sum := sha256.Sum256(hashes)
	if hex.EncodeToString(sum[:]) != str(packetManifest["packet_set_sha256"]) || hex.EncodeToString(sum[:]) != str(maintainer["packet_set_sha256"]) {
		codes = append(codes, "blind_packet_set_hash_mismatch")
	}
	a, e := Canonical(packetManifest["packet_sha256"])
	if e != nil {
		return codes, e
	}
	b, e := Canonical(packetHashes)
	if e != nil {
		return codes, e
	}
	if !bytes.Equal(a, b) {
		codes = append(codes, "blind_packet_inventory_hash_mismatch")
	}
	for _, field := range []string{"annotation_guide_sha256", "decision_schema_sha256", "queue_sha256"} {
		if packetManifest[field] != maintainer[field] {
			codes = append(codes, "blind_packet_provenance_mismatch:"+field)
		}
	}
	// Reviewer artifacts and raw files above are pinned by the immutable public
	// manifest. Validate comparison shape as well; never upgrade its AI evidence.
	comparison, e := checkJSON(filepath.Join(root, "build/adjudication/v1.2/reviewer-comparison.json"))
	if e != nil {
		return codes, e
	}
	schema, e := checkObject(filepath.Join(root, "evals/v1.2/schemas/adjudication-review-comparison.schema.json"))
	if e != nil {
		return codes, e
	}
	codes = append(codes, CheckSchema(schema)...)
	codes = append(codes, ValidateSchema(comparison, schema)...)
	return codes, nil
}

func emptyBlindDecisionForm(v any, path string) bool {
	m, ok := v.(map[string]any)
	if !ok {
		return false
	}
	allowed := map[string]bool{"$.schema": true, "$.protocol_version": true, "$.pair_id": true, "$.locales": true, "$.legacy": true, "$.blinding": true}
	for key, child := range m {
		p := path + "." + key
		if allowed[p] {
			continue
		}
		switch x := child.(type) {
		case map[string]any:
			if !emptyBlindDecisionForm(x, p) {
				return false
			}
		case []any:
			if len(x) > 0 {
				return false
			}
		case string:
			if x != "" {
				return false
			}
		case nil:
		default:
			return false
		}
	}
	return true
}
