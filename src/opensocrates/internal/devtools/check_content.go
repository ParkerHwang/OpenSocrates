package devtools

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func checkContent(root string) ([]string, error) {
	codes := []string{}
	pairs := map[string]string{"compiled-content.bundle.json": "compiled-content-bundle.schema.json", "compiled-response-policy.json": "response-policy.schema.json", "compiled-reasoning-content.bundle.json": "reasoning-content-projections.schema.json"}
	for file, schemaFile := range pairs {
		p := filepath.Join(root, "content", file)
		if _, e := os.Stat(p); e != nil {
			return codes, e
		}
		v, e := checkJSON(p)
		if e != nil {
			return codes, e
		}
		s, e := checkObject(filepath.Join(root, "schemas/v1", schemaFile))
		if e != nil {
			if file == "compiled-response-policy.json" {
				m, ok := v.(map[string]any)
				if !ok || m["schema"] != "opensocrates.response-policy/1.0.0" {
					codes = append(codes, "response_policy_schema_invalid")
				}
				continue
			}
			return codes, e
		}
		if sc := CheckSchema(s); len(sc) > 0 {
			codes = append(codes, sc...)
		} else {
			for _, c := range ValidateSchema(v, s) {
				codes = append(codes, file+":"+c)
			}
		}
	}
	bundle, e := checkObject(filepath.Join(root, "content/compiled-content.bundle.json"))
	if e != nil {
		return codes, e
	}
	tree, e := SourceTreeHash(filepath.Join(root, "content"))
	if e != nil {
		return codes, e
	}
	if bundle["source_tree_hash"] != tree {
		codes = append(codes, "source_tree_hash_mismatch")
	}
	semantic, e := SemanticHash(bundle)
	if e != nil {
		return codes, e
	}
	if bundle["normalized_semantic_hash"] != semantic {
		codes = append(codes, "semantic_hash_mismatch")
	}
	catalog, e := ReadObject(filepath.Join(root, "content/catalog.yaml"))
	if e != nil {
		return codes, e
	}
	teachers, e := ReadObject(filepath.Join(root, "content/teacher-questions.yaml"))
	if e != nil {
		return codes, e
	}
	if e = validateReleasedLocaleSources(root, catalog, teachers); e != nil {
		return codes, e
	}
	methods, ok := bundle["methods"].([]any)
	if !ok || len(methods) != 48 {
		codes = append(codes, "method_count_invalid")
	}
	ids, ok := bundle["method_ids"].([]any)
	if !ok || len(ids) != 48 {
		codes = append(codes, "method_ids_count_invalid")
	}
	seen := map[string]bool{}
	for _, v := range methods {
		m, ok := v.(map[string]any)
		if !ok {
			continue
		}
		id, _ := m["id"].(string)
		if id == "" || seen[id] {
			codes = append(codes, "method_identity_invalid")
		}
		seen[id] = true
		for _, key := range []string{"display_name", "plain_action", "procedure", "complement_fragment"} {
			locales, ok := m[key].(map[string]any)
			if !ok {
				codes = append(codes, "locale_surface_missing:"+id+":"+key)
				continue
			}
			for _, lang := range releasedLocales {
				s, ok := locales[lang].(string)
				if !ok || strings.TrimSpace(s) == "" {
					codes = append(codes, "locale_content_missing:"+id+":"+key+":"+lang)
				}
			}
		}
		if !schemaEqual(m["content_revision"], bundle["content_revision"]) {
			codes = append(codes, "content_revision_mismatch:"+id)
		}
	}
	for _, id := range ids {
		s, ok := id.(string)
		if !ok || !seen[s] {
			codes = append(codes, "method_ids_mismatch")
		}
	}
	projections, e := ReadObject(filepath.Join(root, "content/compiled-reasoning-content.bundle.json"))
	if e != nil {
		return codes, e
	}
	projectionSeen := map[string]bool{}
	for _, raw := range arr(projections["injectable_content"]) {
		entry := obj(raw)
		id, locale := str(entry["method_id"]), str(entry["locale"])
		key := id + ":" + locale
		if !seen[id] || !releasedLocale(locale) || projectionSeen[key] || !schemaEqual(entry["content_revision"], bundle["content_revision"]) {
			codes = append(codes, "locale_projection_identity_invalid")
		}
		projectionSeen[key] = true
	}
	if len(arr(projections["injectable_content"])) != 48*len(releasedLocales) {
		codes = append(codes, "locale_projection_count_invalid")
	}
	for id := range seen {
		for _, locale := range releasedLocales {
			if !projectionSeen[id+":"+locale] {
				codes = append(codes, "locale_projection_missing:"+id+":"+locale)
			}
		}
	}
	for _, key := range []string{"locale_messages", "prompt_fragments"} {
		fields := obj(bundle[key])
		if key == "locale_messages" {
			if len(fields) != len(releasedLocales) {
				codes = append(codes, "locale_message_coverage_invalid")
			}
			for _, locale := range releasedLocales {
				if !schemaEqual(orderedKeys(obj(fields["en"])), orderedKeys(obj(fields[locale]))) {
					codes = append(codes, "locale_message_keys_mismatch:"+locale)
				}
			}
		} else {
			for _, raw := range fields {
				if !exactReleasedLocales(raw) {
					codes = append(codes, "prompt_locale_coverage_invalid")
				}
			}
		}
	}
	// Verify the released baseline receipt when present. It is a frozen inventory,
	// not an instruction to rewrite content owned by another release/session.
	baseline := filepath.Join(root, "docs/v1.6.0/CONTENT_BASELINE.json")
	if _, e := os.Stat(baseline); e == nil {
		m, e := checkObject(baseline)
		if e != nil {
			return codes, e
		}
		for _, field := range []string{"source_tree_hash", "normalized_semantic_hash", "content_revision"} {
			if !schemaEqual(m[field], bundle[field]) {
				codes = append(codes, "released_content_baseline_changed:"+field)
			}
		}
		if hashes, ok := m["files"].(map[string]any); ok {
			for relative, expected := range hashes {
				p, e := safeCheckPath(root, relative)
				if e != nil {
					codes = append(codes, "baseline_path_invalid")
					continue
				}
				b, e := os.ReadFile(p)
				if e != nil {
					return codes, e
				}
				digest := sha256.Sum256(b)
				want, _ := expected.(string)
				if strings.TrimPrefix(want, "sha256:") != hex.EncodeToString(digest[:]) {
					codes = append(codes, "released_content_baseline_changed:"+relative)
				}
			}
		}
	} else {
		codes = append(codes, "released_content_baseline_receipt_missing")
	}
	return codes, nil
}

const adjudicationLockSHA = "15c37de6a0cf8d5377d7e0147bb6f84a56363b3ed23696e38abd9e3e79af52b6"

func checkAdjudication(root, mode string) ([]string, error) {
	if mode != "committed" && mode != "maintainer-evidence" {
		return nil, fmt.Errorf("invalid evidence mode")
	}
	p := filepath.Join(root, "evals/v1.2/adjudication-publication-lock-v1.0.0.json")
	b, e := os.ReadFile(p)
	if e != nil {
		return nil, e
	}
	digest := sha256.Sum256(b)
	if hex.EncodeToString(digest[:]) != adjudicationLockSHA {
		return []string{"publication_trust_root_changed"}, nil
	}
	lock, e := checkObject(p)
	if e != nil {
		return nil, e
	}
	artifacts, ok := lock["artifacts"].(map[string]any)
	if !ok || len(artifacts) != 12 {
		return []string{"publication_inventory_invalid"}, nil
	}
	codes := []string{}
	for name, v := range artifacts {
		m, ok := v.(map[string]any)
		if !ok {
			codes = append(codes, "publication_entry_invalid:"+name)
			continue
		}
		rel, _ := m["path"].(string)
		expected, _ := m["sha256"].(string)
		p, e := safeCheckPath(root, rel)
		if e != nil {
			codes = append(codes, "publication_path_invalid:"+name)
			continue
		}
		b, e := os.ReadFile(p)
		if e != nil {
			return codes, e
		}
		digest := sha256.Sum256(b)
		if hex.EncodeToString(digest[:]) != expected {
			codes = append(codes, "frozen_adjudication_artifact_changed:"+name)
		}
	}
	// Schema assertions and pair cardinality remain independent of publication
	// integrity so future explicit snapshots cannot weaken the evaluation contract.
	for _, spec := range []struct {
		data, schema string
		count        int
	}{{"adjudication-decisions-v1.0.0.jsonl", "adjudication-decision.schema.json", 51}, {"adjudication-disagreements-v1.0.0.jsonl", "adjudication-disagreement.schema.json", 49}} {
		s, e := checkObject(filepath.Join(root, "evals/v1.2/schemas", spec.schema))
		if e != nil {
			return codes, e
		}
		codes = append(codes, CheckSchema(s)...)
		raw, e := os.ReadFile(filepath.Join(root, "evals/v1.2", spec.data))
		if e != nil {
			return codes, e
		}
		rows := bytes.Split(bytes.TrimSpace(raw), []byte{'\n'})
		if len(rows) != spec.count {
			codes = append(codes, "adjudication_record_count_invalid:"+spec.data)
		}
		pairs := map[string]bool{}
		for _, row := range rows {
			d := json.NewDecoder(bytes.NewReader(row))
			d.UseNumber()
			var v map[string]any
			if e := d.Decode(&v); e != nil {
				codes = append(codes, "adjudication_record_json_invalid")
				continue
			}
			codes = append(codes, ValidateSchema(v, s)...)
			id, _ := v["pair_id"].(string)
			if id == "" || pairs[id] {
				codes = append(codes, "adjudication_pair_duplicate")
			}
			pairs[id] = true
		}
	}
	if mode == "maintainer-evidence" {
		more, e := checkMaintainerAdjudication(root)
		codes = append(codes, more...)
		if e != nil {
			return codes, e
		}
	}
	return codes, nil
}
