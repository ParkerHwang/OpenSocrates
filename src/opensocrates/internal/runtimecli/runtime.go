// Package runtimecli exposes native runtime commands independently of the
// installation manager and updater. Default decision and hooks are stateless.
package runtimecli

import (
	"bufio"
	"errors"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/application"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/content"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/decision"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/persistence"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/version"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"
	"unicode/utf8"
)

func emit(out io.Writer, value any) {
	if raw, e := contracts.CanonicalJSON(value); e == nil {
		_, _ = out.Write(raw)
	}
}
func unavailable(code string) map[string]any {
	return map[string]any{"status": "unavailable", "error_code": code}
}
func VersionInfo() map[string]any {
	bundle, err := content.Load()
	if err != nil {
		bundle = nil
	}
	return versionInfoForBundle(bundle)
}
func versionInfoForBundle(bundle *content.Bundle) map[string]any {
	var revision any
	if bundle != nil && bundle.Revision > 0 {
		revision = bundle.Revision
	}
	result := map[string]any{"product": "opensocrates", "product_version": version.ProductVersion, "schema_version": "1.0.0", "schema_major": 1, "content_revision": revision, "router_version": "1.1.0", "verifier_version": "1.0.0", "ruleset_version": "1.0.0"}
	if revision == nil {
		result["content_status"] = "unavailable"
	}
	return result
}
func Run(args []string, in io.Reader, out, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(stderr, "usage: opensocrates <command>")
		return 2
	}
	switch args[0] {
	case "decision":
		if len(args) == 1 {
			return runDecision(in, out, false)
		}
		if len(args) == 2 && args[1] == "--stream" {
			return runDecision(in, out, true)
		}
	case "version":
		if len(args) == 1 {
			fmt.Fprintln(out, version.ProductVersion)
			return 0
		}
		if len(args) == 2 && args[1] == "--json" {
			emit(out, VersionInfo())
			return 0
		}
	case "claude-hook":
		if len(args) == 1 {
			return runClaudeHook(in, out)
		}
	case "hook":
		return runHook(args[1:], in, out)
	case "control":
		return RunControl(args[1:], in, out, stderr)
	case "rigor":
		if len(args) < 2 {
			break
		}
		store := persistence.SettingsStore{Root: persistence.Root()}
		var result any
		switch args[1] {
		case "get":
			if len(args) != 2 {
				break
			}
			result = application.RigorGet(store)
		case "reset":
			if len(args) != 2 {
				break
			}
			result = application.RigorReset(store)
		case "set":
			if len(args) < 3 || len(args) > 4 || !contracts.Is(args[2], "quiet", "together", "strict") || len(args) == 4 && args[3] != "--once" {
				break
			}
			result = application.RigorSet(store, args[2], len(args) == 4)
		}
		if result != nil {
			emit(out, result)
			return 0
		}
	case "metrics":
		return runMetrics(args[1:], out, stderr)
	case "capabilities":
		if len(args) == 4 && contracts.Is(args[1], "show", "probe") && args[2] == "--host" && args[3] == "codex" {
			p := capabilities()
			if args[1] == "probe" {
				p["probe"], p["host"] = "not_run", "codex"
			}
			emit(out, p)
			return 0
		}
	case "diagnose":
		markdown := false
		valid := true
		seen := map[string]bool{}
		for i := 1; i < len(args); i++ {
			switch args[i] {
			case "--json", "--markdown":
				if seen["format"] {
					valid = false
				}
				seen["format"] = true
				markdown = args[i] == "--markdown"
			case "--host":
				if seen["host"] || i+1 >= len(args) || args[i+1] != "codex" {
					valid = false
				} else {
					i++
					seen["host"] = true
				}
			default:
				valid = false
			}
		}
		if valid {
			result := diagnose()
			if markdown {
				fmt.Fprint(out, diagnoseMarkdown(result))
			} else {
				emit(out, result)
			}
			return 0
		}
	case "trace":
		if len(args) == 2 && args[1] == "list" {
			emit(out, map[string]any{"status": "ok", "count": 0})
			return 0
		}
		if len(args) >= 2 && contracts.Is(args[1], "show", "export") {
			emit(out, unavailable("trace_projection_unavailable"))
			return 0
		}
	case "records":
		if len(args) >= 2 {
			switch args[1] {
			case "list", "delete":
				emit(out, unavailable("records_store_unavailable"))
				return 0
			case "prune":
				emit(out, unavailable("records_prune_unavailable"))
				return 0
			}
		}
	}
	fmt.Fprintln(stderr, "invalid command arguments")
	return 2
}
func runDecision(in io.Reader, out io.Writer, stream bool) int {
	bundle, e := content.Load()
	if e != nil {
		emit(out, decision.Failure("canonical_content_unavailable"))
		return 0
	}
	session := decision.New(bundle)
	if !stream {
		raw, e := io.ReadAll(io.LimitReader(in, 16384*4+1))
		if e != nil {
			emit(out, decision.Failure("decision_unavailable"))
			return 0
		}
		if len(raw) == 0 {
			return 0
		}
		if !utf8.Valid(raw) || utf8.RuneCount(raw) > 16384 {
			emit(out, decision.Failure("request_too_large"))
			return 0
		}
		v, e := contracts.Decode(raw)
		if e != nil {
			emit(out, decision.Failure("decision_unavailable"))
		} else {
			emit(out, session.Handle(v))
		}
		return 0
	}
	reader := bufio.NewReaderSize(in, 65537)
	for {
		raw, e := reader.ReadSlice('\n')
		if e == bufio.ErrBufferFull || utf8.RuneCount(raw) > 16384 {
			emit(out, decision.Failure("request_too_large"))
			return 0
		}
		if len(raw) > 0 {
			v, decodeErr := contracts.Decode(raw)
			if decodeErr != nil {
				emit(out, decision.Failure("decision_unavailable"))
			} else {
				emit(out, session.Handle(v))
			}
		}
		if e != nil {
			return 0
		}
	}
}
func capabilities() map[string]any {
	statuses := map[string]any{}
	limits := map[string]any{}
	for _, key := range strings.Fields("prompt_context_injection local_control_execution method_skill_invocation model_initiated_method_skill_activation method_invocation_observation post_tool_observation post_tool_batch_observation completion_candidate_observation bounded_completion_continuation compaction_reinjection published_artifact_confirmation local_record_write deterministic_trace_render rich_card_widget") {
		status, limitation := "unknown", "no-live-probe-receipt"
		switch key {
		case "post_tool_observation":
			status, limitation = "degraded", "documented-tool-observation-gaps"
		case "post_tool_batch_observation":
			limitation = "no-official-equivalent-or-live-receipt"
		case "rich_card_widget":
			status, limitation = "unavailable", "product-contract-no-rich-card-widget"
		}
		statuses[key], limits[key] = status, limitation
	}
	return map[string]any{"status": "ok", "host": "codex_cli", "host_version_range": "unknown", "adapter_version": version.ProductVersion, "checked_at": time.Now().UTC().Format("2006-01-02T15:04:05.000Z"), "computed_tier": "unsupported", "capabilities": statuses, "limitations": limits}
}
func readMetrics() map[string]any {
	data, e := platform.ReadFile(filepath.Join(persistence.Root(), "metrics", "local-events-"+time.Now().UTC().Format("2006-01")+".jsonl"), 16*1024*1024)
	if errors.Is(e, os.ErrNotExist) {
		data = nil
		e = nil
	}
	if e != nil {
		return unavailable("metrics_store_unavailable")
	}
	events, hosts, locales := map[string]any{}, map[string]any{}, map[string]any{}
	count := 0
	for _, line := range strings.Split(string(data), "\n") {
		if line == "" {
			continue
		}
		v, e := contracts.Decode([]byte(line))
		if e != nil {
			return unavailable("metrics_store_unavailable")
		}
		if e = domain.ValidateLocalMetricWire(v); e != nil {
			return unavailable("metrics_store_unavailable")
		}
		m := v.(map[string]any)
		for _, projection := range []struct {
			dest map[string]any
			key  string
		}{{events, "event"}, {hosts, "host"}, {locales, "locale"}} {
			key, _ := m[projection.key].(string)
			n, _ := projection.dest[key].(int)
			projection.dest[key] = n + 1
		}
		count++
	}
	return map[string]any{"status": "ok", "count": count, "events": events, "hosts": hosts, "locales": locales}
}
func runMetrics(args []string, out, stderr io.Writer) int {
	if len(args) == 1 && args[0] == "show" {
		emit(out, readMetrics())
		return 0
	}
	if len(args) == 1 && args[0] == "reset" {
		emit(out, map[string]any{"status": "unsupported", "error_code": "metrics_reset_unavailable"})
		return 0
	}
	if len(args) >= 2 && len(args) <= 3 && args[0] == "export" && (len(args) == 2 || args[2] == "--overwrite") {
		r := readMetrics()
		if r["status"] != "ok" {
			emit(out, r)
			return 0
		}
		payload, e := contracts.CanonicalJSON(r)
		if e == nil {
			e = persistence.SafeExport(args[1], payload, len(args) == 3)
		}
		if e != nil {
			emit(out, map[string]any{"status": "rejected", "error_code": "unsafe_export_destination"})
		} else {
			emit(out, map[string]any{"status": "ok", "exported": true, "count": r["count"]})
		}
		return 0
	}
	fmt.Fprintln(stderr, "invalid metrics arguments")
	return 2
}
func diagnose() map[string]any {
	identities := VersionInfo()
	identities["runtime_version"] = version.ProductVersion
	b, e := content.Load()
	c := map[string]any{"content_revision": nil, "method_count": 0, "source_tree_hash": nil, "normalized_semantic_hash": nil, "status": "unavailable"}
	if e == nil {
		c = map[string]any{"content_revision": b.Revision, "method_count": len(b.IDs), "source_tree_hash": b.SourceTreeHash, "normalized_semantic_hash": b.SemanticHash, "status": "loaded"}
	}
	identities["content"] = c
	health := map[string]any{"status": "healthy", "permissions": "writable", "record_count": 0, "record_bytes": 0, "metric_count": 0, "metric_bytes": 0, "turn_state_count": 0, "quarantine_count": 0, "error_codes": []string{}}
	root := persistence.Root()
	if e := platform.Guard(root); e != nil {
		health["status"], health["permissions"], health["error_codes"] = "unavailable", "unknown", []string{"data_root_unavailable"}
	} else {
		for _, pair := range []struct{ dir, count, bytes string }{{"records", "record_count", "record_bytes"}, {"metrics", "metric_count", "metric_bytes"}, {"runtime/turns", "turn_state_count", ""}, {"quarantine", "quarantine_count", ""}} {
			count, total := 0, int64(0)
			_ = filepath.WalkDir(filepath.Join(root, filepath.FromSlash(pair.dir)), func(path string, entry os.DirEntry, e error) error {
				if e != nil {
					return nil
				}
				if count >= 100000 {
					return filepath.SkipAll
				}
				if entry.Type()&os.ModeSymlink != 0 {
					health["status"], health["error_codes"] = "degraded", []string{"data_root_inspection_limited"}
					if entry.IsDir() {
						return filepath.SkipDir
					}
					return nil
				}
				if entry.Type().IsRegular() {
					count++
					if info, e := entry.Info(); e == nil {
						total += info.Size()
					}
				}
				return nil
			})
			health[pair.count] = count
			if pair.bytes != "" {
				health[pair.bytes] = total
			}
		}
	}
	p := capabilities()
	delete(p, "status")
	p["limitations"] = []string{"documented-tool-observation-gaps", "no-live-probe-receipt", "no-official-equivalent-or-live-receipt", "product-contract-no-rich-card-widget"}
	selector := map[string]any{"status": "unavailable", "attempt_count": nil, "outcome_counts": nil}
	if counts, e := persistence.ReadOutcomes(root); e == nil {
		total := int64(0)
		for _, n := range counts {
			total += n
		}
		if total > 2147483647 {
			total = 2147483647
		}
		status := "not_observed"
		if total > 0 {
			status = "observed"
		}
		selector = map[string]any{"status": status, "attempt_count": total, "outcome_counts": counts}
	}
	osName, arch := runtime.GOOS, runtime.GOARCH
	return map[string]any{"versions": identities, "platform": map[string]any{"os": osName, "architecture": arch}, "capabilities": map[string]any{"codex": p}, "manifest": RuntimeIntegrity("codex"), "selector": selector, "health": health}
}
func diagnoseMarkdown(r map[string]any) string {
	v := r["versions"].(map[string]any)
	h := r["health"].(map[string]any)
	m := r["manifest"].(map[string]any)
	s := r["selector"].(map[string]any)
	attempt := s["attempt_count"]
	if attempt == nil {
		attempt = s["status"]
	}
	return fmt.Sprintf("# OpenSocrates diagnosis\n\n- product: `%v`\n- schema: `%v`\n- content: `%v`\n- manifest: `%v`\n- checksum: `%v`\n- storage: `%v`\n- permissions: `%v`\n- records: `%v` (%v bytes)\n- metrics: `%v` (%v bytes)\n- turn states: `%v`\n- quarantine entries: `%v`\n- selector attempts: `%v`\n", v["product_version"], v["schema_version"], v["content_revision"], m["status"], m["checksum_status"], h["status"], h["permissions"], h["record_count"], h["record_bytes"], h["metric_count"], h["metric_bytes"], h["turn_state_count"], h["quarantine_count"], attempt)
}
