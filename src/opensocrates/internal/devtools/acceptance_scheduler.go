package devtools

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"encoding/csv"
	"encoding/hex"
	"encoding/xml"
	"errors"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
	"io"
	"os"
	"os/user"
	"path/filepath"
	"regexp"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf16"
)

const schedulerFixtureSchema = "opensocrates.native-scheduler-receipt/1.0.0"

func schedulerReceipt(path string) int {
	if !filepath.IsAbs(path) || filepath.Base(path) != "receipt.json" || !strings.HasPrefix(filepath.Base(filepath.Dir(path)), "opensocrates-native-scheduler-") {
		return 2
	}
	if platform.Guard(path) != nil {
		return 2
	}
	if info, e := os.Lstat(filepath.Dir(path)); e != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return 2
	}
	target := nativeAcceptanceTarget()
	if target == "unsupported" {
		return 2
	}
	b, e := Canonical(map[string]any{"schema": schedulerFixtureSchema, "target": target, "native_go_entry_executed": true})
	if e != nil || platform.ExclusiveWrite(path, b, 0600) != nil {
		return 2
	}
	return 0
}
func schedulerXMLText(s string) string {
	var b bytes.Buffer
	_ = xml.EscapeText(&b, []byte(s))
	return b.String()
}
func fixtureLaunchAgent(label, fixture, receipt, work string) []byte {
	return []byte(`<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>` + schedulerXMLText(label) + `</string><key>ProgramArguments</key><array><string>` + schedulerXMLText(fixture) + `</string><string>--scheduler-receipt</string><string>` + schedulerXMLText(receipt) + `</string></array><key>WorkingDirectory</key><string>` + schedulerXMLText(work) + `</string><key>RunAtLoad</key><true/><key>ProcessType</key><string>Background</string><key>StandardOutPath</key><string>/dev/null</string><key>StandardErrorPath</key><string>/dev/null</string></dict></plist>
`)
}
func fixtureWindowsArguments(receipt string) string { return `--scheduler-receipt "` + receipt + `"` }
func fixtureWindowsTask(id, fixture, receipt, sid string) []byte {
	return []byte(`<?xml version="1.0" encoding="UTF-8"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><RegistrationInfo><Description>OpenSocrates isolated native scheduler fixture ` + id + `</Description></RegistrationInfo><Triggers><LogonTrigger><Enabled>true</Enabled><Repetition><Interval>PT24H</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition><UserId>` + schedulerXMLText(sid) + `</UserId><Delay>PT5M</Delay></LogonTrigger></Triggers><Principals><Principal id="User"><UserId>` + schedulerXMLText(sid) + `</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals><Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><AllowStartOnDemand>true</AllowStartOnDemand><Enabled>true</Enabled><ExecutionTimeLimit>PT2M</ExecutionTimeLimit></Settings><Actions Context="User"><Exec><Command>` + schedulerXMLText(fixture) + `</Command><Arguments>` + schedulerXMLText(fixtureWindowsArguments(receipt)) + `</Arguments></Exec></Actions></Task>
`)
}
func schedulerWindowsText(raw []byte) []byte {
	if len(raw) >= 2 && raw[0] == 0xff && raw[1] == 0xfe {
		raw = raw[2:]
	} else if len(raw) < 2 || raw[1] != 0 {
		return bytes.TrimPrefix(raw, []byte{0xef, 0xbb, 0xbf})
	}
	if len(raw)%2 != 0 {
		return nil
	}
	words := make([]uint16, len(raw)/2)
	for i := range words {
		words[i] = binary.LittleEndian.Uint16(raw[2*i:])
	}
	return []byte(string(utf16.Decode(words)))
}
func ownedFixtureWindowsTask(raw []byte, id, fixture, receipt, sid string) bool {
	var doc struct {
		RegistrationInfo struct {
			Description string `xml:"Description"`
		} `xml:"RegistrationInfo"`
		Principals []struct {
			ID        string  `xml:"id,attr"`
			UserID    string  `xml:"UserId"`
			LogonType string  `xml:"LogonType"`
			RunLevel  *string `xml:"RunLevel"`
		} `xml:"Principals>Principal"`
		Triggers []struct {
			Enabled    *bool `xml:"Enabled"`
			Repetition struct {
				Interval          string `xml:"Interval"`
				Duration          string `xml:"Duration"`
				StopAtDurationEnd bool   `xml:"StopAtDurationEnd"`
			} `xml:"Repetition"`
			UserID string `xml:"UserId"`
			Delay  string `xml:"Delay"`
		} `xml:"Triggers>LogonTrigger"`
		Actions struct {
			Context string `xml:"Context,attr"`
			Exec    []struct {
				Command   string `xml:"Command"`
				Arguments string `xml:"Arguments"`
			} `xml:"Exec"`
		} `xml:"Actions"`
	}
	if xml.Unmarshal(bytes.ReplaceAll(schedulerWindowsText(raw), []byte(`encoding="UTF-16"`), []byte(`encoding="UTF-8"`)), &doc) != nil {
		return false
	}
	if !fixtureTaskClosedPolicy(raw, id, fixture, receipt, sid) {
		return false
	}
	if doc.RegistrationInfo.Description != "OpenSocrates isolated native scheduler fixture "+id || len(doc.Principals) != 1 || len(doc.Actions.Exec) != 1 || len(doc.Triggers) != 1 {
		return false
	}
	p := doc.Principals[0]
	trigger := doc.Triggers[0]
	// Scheduler exports may omit the schema-default true Enabled value.
	enabled := trigger.Enabled == nil || *trigger.Enabled
	if !enabled || trigger.UserID != sid || trigger.Delay != "PT5M" || (trigger.Repetition.Interval != "PT24H" && trigger.Repetition.Interval != "P1D") || trigger.Repetition.Duration != "" || trigger.Repetition.StopAtDurationEnd {
		return false
	}
	action := doc.Actions.Exec[0]
	// The Task Scheduler schema defaults an omitted RunLevel to LeastPrivilege.
	// An explicit empty/unknown/elevated value is never equivalent to omission.
	leastPrivilege := p.RunLevel == nil || (p.RunLevel != nil && *p.RunLevel == "LeastPrivilege")
	return p.ID != "" && p.UserID == sid && p.LogonType == "InteractiveToken" && leastPrivilege && doc.Actions.Context == p.ID && action.Command == fixture && action.Arguments == fixtureWindowsArguments(receipt)
}

// Only the fixture policy and observed/documented Scheduler defaults are
// eligible for removal. An extra trigger, action, attribute or changed setting
// cannot inherit ownership from the description marker.
func fixtureTaskClosedPolicy(raw []byte, id, fixture, receipt, sid string) bool {
	values := map[string]string{
		"Task/RegistrationInfo/Description":                       "OpenSocrates isolated native scheduler fixture " + id,
		"Task/RegistrationInfo/URI":                               `\OpenSocratesAcceptance-` + id,
		"Task/Principals/Principal/UserId":                        sid,
		"Task/Principals/Principal/LogonType":                     "InteractiveToken",
		"Task/Principals/Principal/RunLevel":                      "LeastPrivilege",
		"Task/Triggers/LogonTrigger/Enabled":                      "true",
		"Task/Triggers/LogonTrigger/Repetition/Interval":          "PT24H",
		"Task/Triggers/LogonTrigger/Repetition/StopAtDurationEnd": "false",
		"Task/Triggers/LogonTrigger/UserId":                       sid,
		"Task/Triggers/LogonTrigger/Delay":                        "PT5M",
		"Task/Triggers/LogonTrigger/ExecutionTimeLimit":           "PT72H",
		"Task/Settings/MultipleInstancesPolicy":                   "IgnoreNew",
		"Task/Settings/DisallowStartIfOnBatteries":                "false",
		"Task/Settings/StopIfGoingOnBatteries":                    "false",
		"Task/Settings/AllowStartOnDemand":                        "true",
		"Task/Settings/Enabled":                                   "true",
		"Task/Settings/ExecutionTimeLimit":                        "PT2M",
		"Task/Settings/AllowHardTerminate":                        "true",
		"Task/Settings/StartWhenAvailable":                        "false",
		"Task/Settings/RunOnlyIfNetworkAvailable":                 "false",
		"Task/Settings/RunOnlyIfIdle":                             "false",
		"Task/Settings/WakeToRun":                                 "false",
		"Task/Settings/Hidden":                                    "false",
		"Task/Settings/Priority":                                  "7",
		"Task/Settings/DisallowStartOnRemoteAppSession":           "false",
		"Task/Settings/IdleSettings/Duration":                     "PT10M",
		"Task/Settings/IdleSettings/WaitTimeout":                  "PT1H",
		"Task/Settings/IdleSettings/StopOnIdleEnd":                "true",
		"Task/Settings/IdleSettings/RestartOnIdle":                "false",
		"Task/Actions/Exec/Command":                               fixture,
		"Task/Actions/Exec/Arguments":                             fixtureWindowsArguments(receipt),
	}
	containers := map[string]bool{}
	for _, path := range strings.Fields("Task Task/RegistrationInfo Task/Principals Task/Principals/Principal Task/Triggers Task/Triggers/LogonTrigger Task/Triggers/LogonTrigger/Repetition Task/Settings Task/Settings/IdleSettings Task/Actions Task/Actions/Exec") {
		containers[path] = true
	}
	decoder := xml.NewDecoder(bytes.NewReader(bytes.ReplaceAll(schedulerWindowsText(raw), []byte(`encoding="UTF-16"`), []byte(`encoding="UTF-8"`))))
	stack := []string{}
	seen := map[string]bool{}
	texts := []*strings.Builder{}
	for {
		token, err := decoder.Token()
		if err == io.EOF {
			return len(stack) == 0 && seen["Task"]
		}
		if err != nil {
			return false
		}
		switch value := token.(type) {
		case xml.StartElement:
			if value.Name.Space != "http://schemas.microsoft.com/windows/2004/02/mit/task" {
				return false
			}
			stack = append(stack, value.Name.Local)
			path := strings.Join(stack, "/")
			_, leaf := values[path]
			if seen[path] || (!containers[path] && !leaf && path != "Task/Settings/UseUnifiedSchedulingEngine") {
				return false
			}
			seen[path] = true
			for _, attr := range value.Attr {
				if attr.Name.Local == "xmlns" && path == "Task" && attr.Value == value.Name.Space {
					continue
				}
				if attr.Name.Space != "" {
					return false
				}
				if path == "Task" && attr.Name.Local == "version" && attr.Value == "1.4" {
					continue
				}
				if path == "Task/Principals/Principal" && attr.Name.Local == "id" && attr.Value == "User" {
					continue
				}
				if path == "Task/Actions" && attr.Name.Local == "Context" && attr.Value == "User" {
					continue
				}
				return false
			}
			texts = append(texts, &strings.Builder{})
		case xml.CharData:
			if len(texts) > 0 {
				texts[len(texts)-1].Write(value)
			} else if len(bytes.TrimSpace(value)) > 0 {
				return false
			}
		case xml.EndElement:
			path := strings.Join(stack, "/")
			text := strings.TrimSpace(texts[len(texts)-1].String())
			if containers[path] {
				if text != "" {
					return false
				}
			} else if path == "Task/Settings/UseUnifiedSchedulingEngine" {
				// The OS may select the engine for this imported version; both
				// representations retain the same fixed action/trigger policy.
				if text != "true" && text != "false" {
					return false
				}
			} else {
				if path == "Task/Triggers/LogonTrigger/Repetition/Interval" && text == "P1D" {
					text = "PT24H"
				}
				if text != values[path] {
					return false
				}
			}
			stack = stack[:len(stack)-1]
			texts = texts[:len(texts)-1]
		case xml.Directive:
			return false
		}
	}
}
func readSchedulerReceipt(path, target string) bool {
	b, e := platform.ReadFile(path, 4096)
	if e != nil {
		return false
	}
	v, e := contractsSchedulerReceipt(b)
	if e != nil {
		return false
	}
	return len(v) == 3 && v["schema"] == schedulerFixtureSchema && v["target"] == target && v["native_go_entry_executed"] == true
}
func contractsSchedulerReceipt(b []byte) (map[string]any, error) {
	value, e := contracts.Decode(b)
	if e != nil {
		return nil, e
	}
	v, ok := value.(map[string]any)
	if !ok {
		return nil, errors.New("scheduler_receipt_invalid")
	}
	return v, nil
}
func awaitSchedulerReceipt(path, target string) bool {
	deadline := time.Now().Add(20 * time.Second)
	for time.Now().Before(deadline) {
		if readSchedulerReceipt(path, target) {
			return true
		}
		time.Sleep(100 * time.Millisecond)
	}
	return false
}

// nativeSchedulerAcceptance exercises a disposable OS registration and a native
// Go entry. Its unique label/task cannot address the production updater job.
func nativeSchedulerAcceptance(o acceptanceOptions) (report map[string]any, err error) {
	target := nativeAcceptanceTarget()
	report = map[string]any{"target": target, "evidence_scope": "isolated_native_os_scheduler_fixture", "live_host_delivery_claimed": false, "production_update_run_claimed": false, "user_installation_modified": false, "pass": false, "cases": map[string]any{}}
	if target == "unsupported" || o.hostBinary == "" {
		delete(report, "pass")
		return report, errors.New("native_scheduler_fixture_required")
	}
	fixture, e := filepath.Abs(o.hostBinary)
	if e != nil {
		delete(report, "pass")
		return report, errors.New("native_scheduler_fixture_unavailable")
	}
	var token [16]byte
	if _, e = rand.Read(token[:]); e != nil {
		return report, e
	}
	id := hex.EncodeToString(token[:])
	report["fixture_id"] = id
	root, e := platform.MkdirTemp("", "opensocrates-native-scheduler-"+id+"-")
	if e != nil {
		return report, e
	}
	if e = platform.Guard(root); e != nil {
		return report, e
	}
	ownedFixture := filepath.Join(root, "native-scheduler-entry")
	if runtime.GOOS == "windows" {
		ownedFixture += ".exe"
	}
	if e = copyAcceptanceTree(fixture, ownedFixture); e != nil {
		_ = platform.RemoveTree(root)
		return report, e
	}
	fixture = ownedFixture
	report["fixture_preparation"] = "private_owned_copy_of_explicit_go_fixture"
	receipt := filepath.Join(root, "receipt.json")
	cases := report["cases"].(map[string]any)
	registered := false
	cleaned := false
	record := func(name string, passed bool) { cases[name] = map[string]any{"pass": passed} }
	ctx, cancel := context.WithTimeout(context.Background(), 70*time.Second)
	defer cancel()
	run := func(exe string, args ...string) ([]byte, error) {
		commandCtx, commandCancel := context.WithTimeout(ctx, 15*time.Second)
		defer commandCancel()
		result, e := platform.Run(commandCtx, exe, args, platform.RunOptions{OutputLimit: 1 << 20})
		return result.Stdout, e
	}
	if runtime.GOOS == "darwin" {
		tool, e := platform.SystemExecutable("launchctl")
		if e != nil {
			delete(report, "pass")
			return report, e
		}
		label := "com.opensocrates.acceptance." + id
		domain := fmt.Sprintf("gui/%d", os.Getuid())
		service := domain + "/" + label
		domainBefore, domainErr := run(tool, "print", domain)
		if domainErr != nil {
			delete(report, "pass")
			_ = platform.RemoveTree(root)
			return report, errors.New("native_user_launchd_domain_unavailable")
		}
		if bytes.Contains(domainBefore, []byte(label)) {
			_ = platform.RemoveTree(root)
			return report, errors.New("scheduler_fixture_identity_collision")
		}
		plist := filepath.Join(root, "fixture.plist")
		document := fixtureLaunchAgent(label, fixture, receipt, root)
		if e = platform.ExclusiveWrite(plist, document, 0600); e != nil {
			return report, e
		}
		defer func() {
			actual, e := platform.ReadFile(plist, 1<<20)
			docOwned := e == nil && bytes.Equal(actual, document)
			if docOwned {
				output, inspectErr := schedulerCleanupRun(tool, "print", service)
				if inspectErr != nil {
					domainOutput, domainErr := schedulerCleanupRun(tool, "print", domain)
					cleaned = domainErr == nil && !bytes.Contains(domainOutput, []byte(label))
				} else if bytes.Contains(output, []byte(label)) && bytes.Contains(output, []byte(fixture)) {
					_, removeErr := schedulerCleanupRun(tool, "bootout", service)
					if removeErr == nil {
						domainOutput, domainErr := schedulerCleanupRun(tool, "print", domain)
						cleaned = domainErr == nil && !bytes.Contains(domainOutput, []byte(label))
					}
				}
			}
			record("exact_owned_cleanup", cleaned)
			if cleaned {
				_ = platform.RemoveTree(root)
			} else {
				report["pass"] = false
				report["cleanup_required"] = true
				err = errors.New("scheduler_fixture_cleanup_incomplete")
			}
		}()
		_, e = run(tool, "bootstrap", domain, plist)
		registered = e == nil
		record("native_registration", registered)
		if !registered {
			return report, errors.New("scheduler_fixture_registration_failed")
		}
		output, e := run(tool, "print", service)
		owned := e == nil && bytes.Contains(output, []byte(label)) && bytes.Contains(output, []byte(fixture))
		record("registration_identity_verified", owned)
		executed := awaitSchedulerReceipt(receipt, target)
		record("native_go_entry_executed", executed)
		report["pass"] = registered && owned && executed
		return report, nil
	}
	tool, e := platform.SystemExecutable("schtasks.exe")
	if e != nil {
		delete(report, "pass")
		return report, e
	}
	identity, e := user.Current()
	if e != nil || !strings.HasPrefix(identity.Uid, "S-1-") {
		delete(report, "pass")
		return report, errors.New("native_scheduler_user_identity_unavailable")
	}
	task := "OpenSocratesAcceptance-" + id
	allTasks, listErr := run(tool, "/Query", "/FO", "CSV", "/NH")
	if listErr != nil || !schedulerTaskAbsent(allTasks, task) {
		_ = platform.RemoveTree(root)
		return report, errors.New("scheduler_fixture_identity_collision")
	}
	document := fixtureWindowsTask(id, fixture, receipt, identity.Uid)
	importDocument, e := update.EncodeTaskImportXML(document)
	if e != nil {
		return report, e
	}
	xmlPath := filepath.Join(root, "fixture-task.xml")
	if e = platform.ExclusiveWrite(xmlPath, importDocument, 0600); e != nil {
		return report, e
	}
	defer func() {
		raw, e := schedulerCleanupRun(tool, "/Query", "/TN", task, "/XML")
		if e != nil {
			all, allErr := schedulerCleanupRun(tool, "/Query", "/FO", "CSV", "/NH")
			cleaned = allErr == nil && schedulerTaskAbsent(all, task)
		} else if ownedFixtureWindowsTask(raw, id, fixture, receipt, identity.Uid) {
			_, removeErr := schedulerCleanupRun(tool, "/Delete", "/TN", task, "/F")
			if removeErr == nil {
				all, allErr := schedulerCleanupRun(tool, "/Query", "/FO", "CSV", "/NH")
				cleaned = allErr == nil && schedulerTaskAbsent(all, task)
			}
		}
		record("exact_owned_cleanup", cleaned)
		if cleaned {
			_ = platform.RemoveTree(root)
		} else {
			report["pass"] = false
			report["cleanup_required"] = true
			err = errors.New("scheduler_fixture_cleanup_incomplete")
		}
	}()
	registrationContext, registrationCancel := context.WithTimeout(ctx, 15*time.Second)
	registrationResult, registrationError := platform.Run(registrationContext, tool, []string{"/Create", "/TN", task, "/XML", xmlPath, "/HResult"}, platform.RunOptions{OutputLimit: 1 << 20})
	registrationCancel()
	e = registrationError
	registered = e == nil
	record("native_registration", registered)
	if !registered {
		cases["native_registration"].(map[string]any)["diagnostic"] = schedulerRegistrationDiagnostic(registrationResult, registrationError)
	}
	if !registered {
		return report, errors.New("scheduler_fixture_registration_failed")
	}
	raw, e := run(tool, "/Query", "/TN", task, "/XML")
	if e == nil {
		report["native_query_projection"] = schedulerQueryProjection(raw, document)
	}
	owned := e == nil && ownedFixtureWindowsTask(raw, id, fixture, receipt, identity.Uid)
	record("registration_identity_verified", owned)
	if !owned {
		return report, errors.New("scheduler_fixture_identity_unverified")
	}
	_, e = run(tool, "/Run", "/TN", task)
	executed := e == nil && awaitSchedulerReceipt(receipt, target)
	record("native_go_entry_executed", executed)
	if !executed {
		return report, errors.New("scheduler_fixture_entry_unverified")
	}
	// Capture and restore the OS-exported document, retaining every OS default
	// and unknown field. A second query must match the entire captured tree
	// before this unique test registration can be removed.
	captured, e := run(tool, "/Query", "/TN", task, "/XML")
	if e != nil || !ownedFixtureWindowsTask(captured, id, fixture, receipt, identity.Uid) || !update.TaskDocumentMatches(captured, raw, fixture) {
		return report, errors.New("scheduler_fixture_capture_changed")
	}
	canonicalCaptured := bytes.ReplaceAll(schedulerWindowsText(captured), []byte(`encoding="UTF-16"`), []byte(`encoding="UTF-8"`))
	restoreTransport, e := update.EncodeTaskImportXML(canonicalCaptured)
	if e != nil {
		return report, errors.New("scheduler_fixture_export_invalid")
	}
	restorePath := filepath.Join(root, "restored-task.xml")
	if e = platform.ExclusiveWrite(restorePath, restoreTransport, 0600); e != nil {
		return report, e
	}
	if _, e = run(tool, "/Delete", "/TN", task, "/F"); e != nil {
		return report, e
	}
	all, e := run(tool, "/Query", "/FO", "CSV", "/NH")
	if e != nil || !schedulerTaskAbsent(all, task) {
		return report, errors.New("scheduler_fixture_restore_absence_unverified")
	}
	if _, e = run(tool, "/Create", "/TN", task, "/XML", restorePath, "/HResult"); e != nil {
		return report, errors.New("scheduler_fixture_restore_failed")
	}
	restored, e := run(tool, "/Query", "/TN", task, "/XML")
	roundtrip := e == nil && ownedFixtureWindowsTask(restored, id, fixture, receipt, identity.Uid) && update.TaskDocumentMatches(restored, captured, fixture)
	record("native_export_import_restore_roundtrip", roundtrip)
	if !roundtrip {
		return report, errors.New("scheduler_fixture_restore_changed")
	}
	report["restored_query_projection"] = schedulerQueryProjection(restored, document)
	report["pass"] = registered && owned && executed && roundtrip
	return report, nil
}

// Expose only schema structure and approved nonpersonal settings. Account,
// author, description, URI, action/argument and network values stay private.
func schedulerQueryProjection(raw, canonical []byte) map[string]any {
	rawHash := sha256.Sum256(raw)
	canonicalHash := sha256.Sum256(canonical)
	report := map[string]any{"query_sha256": hex.EncodeToString(rawHash[:]), "canonical_sha256": hex.EncodeToString(canonicalHash[:])}
	known := map[string]bool{}
	for _, name := range strings.Fields("Task RegistrationInfo Date Author Description URI Source Version SecurityDescriptor Triggers LogonTrigger Enabled Repetition Interval Duration StopAtDurationEnd UserId Delay StartBoundary EndBoundary ExecutionTimeLimit Principals Principal LogonType RunLevel DisplayName GroupId ProcessTokenSidType RequiredPrivileges Privilege Settings MultipleInstancesPolicy DisallowStartIfOnBatteries StopIfGoingOnBatteries AllowStartOnDemand AllowHardTerminate StartWhenAvailable RunOnlyIfNetworkAvailable IdleSettings StopOnIdleEnd RestartOnIdle WaitTimeout NetworkSettings Name Id RestartOnFailure Count Priority RunOnlyIfIdle WakeToRun Hidden UseUnifiedSchedulingEngine DisallowStartOnRemoteAppSession Volatile MaintenanceSettings Period Deadline Exclusive Actions Exec Command Arguments WorkingDirectory") {
		known[name] = true
	}
	boolean := map[string]bool{}
	for _, name := range strings.Fields("Enabled DisallowStartIfOnBatteries StopIfGoingOnBatteries AllowStartOnDemand AllowHardTerminate StartWhenAvailable RunOnlyIfNetworkAvailable StopOnIdleEnd RestartOnIdle RunOnlyIfIdle WakeToRun Hidden UseUnifiedSchedulingEngine DisallowStartOnRemoteAppSession Volatile Exclusive StopAtDurationEnd") {
		boolean[name] = true
	}
	settings := map[string]any{}
	paths := map[string]bool{}
	stack := []string{}
	var text strings.Builder
	unknown := 0
	decoded := bytes.ReplaceAll(schedulerWindowsText(raw), []byte(`encoding="UTF-16"`), []byte(`encoding="UTF-8"`))
	decoder := xml.NewDecoder(bytes.NewReader(decoded))
	valid := true
	for {
		token, e := decoder.Token()
		if e != nil {
			if e.Error() != "EOF" {
				valid = false
			}
			break
		}
		switch value := token.(type) {
		case xml.StartElement:
			stack = append(stack, value.Name.Local)
			text.Reset()
			pathKnown := true
			for _, part := range stack {
				pathKnown = pathKnown && known[part]
			}
			if pathKnown {
				paths[strings.Join(stack, "/")] = true
			} else {
				unknown++
			}
			if len(stack) == 1 {
				for _, attr := range value.Attr {
					if attr.Name.Local == "version" && regexp.MustCompile(`^1\.[0-9]$`).MatchString(attr.Value) {
						report["task_version"] = attr.Value
					}
				}
			}
		case xml.CharData:
			text.Write(value)
		case xml.EndElement:
			if len(stack) == 0 {
				valid = false
				continue
			}
			path := strings.Join(stack, "/")
			leaf := stack[len(stack)-1]
			data := strings.TrimSpace(text.String())
			safePath := strings.HasPrefix(path, "Task/Settings/") || path == "Task/Triggers/LogonTrigger/Delay" || path == "Task/Triggers/LogonTrigger/Repetition/Interval"
			if safePath {
				if boolean[leaf] && (data == "true" || data == "false") {
					settings[path] = data == "true"
				} else if leaf == "Priority" || leaf == "Count" {
					if n, e := strconv.Atoi(data); e == nil && n >= 0 && n <= 100 {
						settings[path] = n
					}
				} else if leaf == "MultipleInstancesPolicy" {
					for _, allowed := range []string{"IgnoreNew", "Parallel", "Queue", "StopExisting"} {
						if data == allowed {
							settings[path] = data
						}
					}
				} else if regexp.MustCompile(`^P(?:[0-9]{1,4}D)?(?:T(?:[0-9]{1,4}H)?(?:[0-9]{1,4}M)?(?:[0-9]{1,4}S)?)?$`).MatchString(data) && len(data) <= 32 {
					settings[path] = data
				}
			}
			stack = stack[:len(stack)-1]
			text.Reset()
		}
	}
	names := []string{}
	for path := range paths {
		names = append(names, path)
	}
	sort.Strings(names)
	report["structure_paths"] = names
	report["approved_settings"] = settings
	report["unknown_tag_count"] = unknown
	report["xml_parsed"] = valid
	return report
}

// This projection never returns OS output, paths, account identifiers or
// arbitrary error text. /HResult gives a locale-independent numeric outcome.
func schedulerRegistrationDiagnostic(result platform.Result, err error) map[string]any {
	category := "none"
	if err != nil {
		category = string(diagnostics.CodeOf(err))
	}
	stdoutHash := sha256.Sum256(result.Stdout)
	stderrHash := sha256.Sum256(result.Stderr)
	status := uint32(result.ExitCode)
	classification := "unclassified"
	switch status {
	case 0x80070005:
		classification = "access_denied"
	case 0x80070534:
		classification = "account_unmapped"
	case 0x80041316:
		classification = "xml_node_unexpected"
	case 0x80041317:
		classification = "xml_namespace_invalid"
	case 0x80041318:
		classification = "xml_value_invalid"
	case 0x80041319:
		classification = "xml_required_node_missing"
	case 0x8004131a:
		classification = "xml_malformed"
	case 0x80070057:
		classification = "invalid_parameter"
	}
	report := map[string]any{"error_category": category, "exit_code": result.ExitCode, "hresult": fmt.Sprintf("0x%08x", status), "known_error_class": classification, "stdout_len": len(result.Stdout), "stderr_len": len(result.Stderr), "stdout_sha256": hex.EncodeToString(stdoutHash[:]), "stderr_sha256": hex.EncodeToString(stderrHash[:])}
	text := string(schedulerWindowsText(append(append([]byte(nil), result.Stdout...), result.Stderr...)))
	if match := regexp.MustCompile(`\(([0-9]{1,6}),([0-9]{1,6})\)`).FindStringSubmatch(text); len(match) == 3 {
		line, _ := strconv.Atoi(match[1])
		column, _ := strconv.Atoi(match[2])
		report["xml_line"] = line
		report["xml_column"] = column
	}
	return report
}

func schedulerCleanupRun(exe string, args ...string) ([]byte, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	result, e := platform.Run(ctx, exe, args, platform.RunOptions{OutputLimit: 1 << 20})
	return result.Stdout, e
}
func schedulerTaskAbsent(raw []byte, name string) bool {
	rows, e := csv.NewReader(bytes.NewReader(schedulerWindowsText(raw))).ReadAll()
	if e != nil {
		return false
	}
	for _, row := range rows {
		if len(row) < 3 {
			return false
		}
		if row[0] == name || row[0] == "\\"+name {
			return false
		}
	}
	return true
}

func schedulerCleanupDefinition(raw []byte, id, sid string) (string, string, bool) {
	if !regexp.MustCompile(`^[0-9a-f]{32}$`).MatchString(id) {
		return "", "", false
	}
	var doc struct {
		Actions []struct {
			Command   string `xml:"Command"`
			Arguments string `xml:"Arguments"`
		} `xml:"Actions>Exec"`
	}
	decoded := bytes.ReplaceAll(schedulerWindowsText(raw), []byte(`encoding="UTF-16"`), []byte(`encoding="UTF-8"`))
	if xml.Unmarshal(decoded, &doc) != nil || len(doc.Actions) != 1 {
		return "", "", false
	}
	command := doc.Actions[0].Command
	root := filepath.Dir(command)
	receipt := filepath.Join(root, "receipt.json")
	prefix := "opensocrates-native-scheduler-" + id + "-"
	if !filepath.IsAbs(command) || filepath.Base(command) != "native-scheduler-entry.exe" || !strings.HasPrefix(filepath.Base(root), prefix) || len(filepath.Base(root)) <= len(prefix) || doc.Actions[0].Arguments != fixtureWindowsArguments(receipt) {
		return "", "", false
	}
	if !ownedFixtureWindowsTask(raw, id, command, receipt, sid) {
		return "", "", false
	}
	return root, command, true
}

func nativeSchedulerFixtureCleanup(id string) (map[string]any, error) {
	report := map[string]any{"target": nativeAcceptanceTarget(), "evidence_scope": "exact_prior_isolated_scheduler_fixture_cleanup", "production_update_run_claimed": false, "user_installation_modified": false, "pass": false}
	if runtime.GOOS != "windows" || !regexp.MustCompile(`^[0-9a-f]{32}$`).MatchString(id) {
		return report, errors.New("fixture_cleanup_scope_invalid")
	}
	report["fixture_id"] = id
	tool, e := platform.SystemExecutable("schtasks.exe")
	if e != nil {
		return report, e
	}
	task := "OpenSocratesAcceptance-" + id
	all, e := schedulerCleanupRun(tool, "/Query", "/FO", "CSV", "/NH")
	if e != nil {
		return report, e
	}
	if schedulerTaskAbsent(all, task) {
		report["pass"] = true
		report["task_already_absent"] = true
		return report, nil
	}
	raw, e := schedulerCleanupRun(tool, "/Query", "/TN", task, "/XML")
	if e != nil {
		return report, e
	}
	identity, e := user.Current()
	if e != nil {
		return report, e
	}
	root, fixture, owned := schedulerCleanupDefinition(raw, id, identity.Uid)
	if !owned || platform.Guard(root) != nil || platform.GuardOwned(fixture) != nil {
		return report, errors.New("fixture_cleanup_identity_unverified")
	}
	rootInfo, rootError := os.Lstat(root)
	fixtureInfo, fixtureError := os.Lstat(fixture)
	if rootError != nil || !rootInfo.IsDir() || rootInfo.Mode()&os.ModeSymlink != 0 || fixtureError != nil || !fixtureInfo.Mode().IsRegular() || fixtureInfo.Size() == 0 {
		return report, errors.New("fixture_cleanup_object_invalid")
	}
	// Refuse unknown or changed local objects. These files are fixture-owned;
	// no parent, host state, npm package or production task may be targeted.
	entries, e := os.ReadDir(root)
	if e != nil {
		return report, e
	}
	for _, entry := range entries {
		if entry.IsDir() {
			return report, errors.New("fixture_cleanup_foreign_object")
		}
		switch entry.Name() {
		case "native-scheduler-entry.exe":
		case "fixture-task.xml", "restored-task.xml":
			data, e := platform.ReadFile(filepath.Join(root, entry.Name()), 1<<20)
			if e != nil || !ownedFixtureWindowsTask(data, id, fixture, filepath.Join(root, "receipt.json"), identity.Uid) {
				return report, errors.New("fixture_cleanup_changed_definition")
			}
		case "receipt.json":
			if !readSchedulerReceipt(filepath.Join(root, entry.Name()), "windows-x64") {
				return report, errors.New("fixture_cleanup_changed_receipt")
			}
		default:
			return report, errors.New("fixture_cleanup_foreign_object")
		}
	}
	fresh, e := schedulerCleanupRun(tool, "/Query", "/TN", task, "/XML")
	if e != nil || !update.TaskDocumentMatches(fresh, raw, fixture) {
		return report, errors.New("fixture_cleanup_task_changed")
	}
	if _, e = schedulerCleanupRun(tool, "/Delete", "/TN", task, "/F"); e != nil {
		return report, e
	}
	all, e = schedulerCleanupRun(tool, "/Query", "/FO", "CSV", "/NH")
	if e != nil || !schedulerTaskAbsent(all, task) {
		return report, errors.New("fixture_cleanup_absence_unverified")
	}
	if e = platform.RemoveTree(root); e != nil {
		return report, e
	}
	report["pass"] = true
	report["exact_owned_cleanup"] = true
	return report, nil
}
