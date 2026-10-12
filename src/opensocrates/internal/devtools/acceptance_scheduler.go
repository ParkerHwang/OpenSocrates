package devtools

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/binary"
	"encoding/csv"
	"encoding/hex"
	"encoding/xml"
	"errors"
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/contracts"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"os"
	"os/user"
	"path/filepath"
	"runtime"
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
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><RegistrationInfo><Description>OpenSocrates isolated native scheduler fixture ` + id + `</Description></RegistrationInfo><Principals><Principal id="User"><UserId>` + schedulerXMLText(sid) + `</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals><Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><AllowStartOnDemand>true</AllowStartOnDemand><Enabled>true</Enabled><ExecutionTimeLimit>PT2M</ExecutionTimeLimit></Settings><Actions Context="User"><Exec><Command>` + schedulerXMLText(fixture) + `</Command><Arguments>` + schedulerXMLText(fixtureWindowsArguments(receipt)) + `</Arguments></Exec></Actions></Task>
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
			ID        string `xml:"id,attr"`
			UserID    string `xml:"UserId"`
			LogonType string `xml:"LogonType"`
			RunLevel  string `xml:"RunLevel"`
		} `xml:"Principals>Principal"`
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
	if doc.RegistrationInfo.Description != "OpenSocrates isolated native scheduler fixture "+id || len(doc.Principals) != 1 || len(doc.Actions.Exec) != 1 {
		return false
	}
	p := doc.Principals[0]
	action := doc.Actions.Exec[0]
	return p.ID != "" && p.UserID == sid && p.LogonType == "InteractiveToken" && p.RunLevel == "LeastPrivilege" && doc.Actions.Context == p.ID && action.Command == fixture && action.Arguments == fixtureWindowsArguments(receipt)
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
	xmlPath := filepath.Join(root, "fixture-task.xml")
	if e = platform.ExclusiveWrite(xmlPath, document, 0600); e != nil {
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
	_, e = run(tool, "/Create", "/TN", task, "/XML", xmlPath)
	registered = e == nil
	record("native_registration", registered)
	if !registered {
		return report, errors.New("scheduler_fixture_registration_failed")
	}
	raw, e := run(tool, "/Query", "/TN", task, "/XML")
	owned := e == nil && ownedFixtureWindowsTask(raw, id, fixture, receipt, identity.Uid)
	record("registration_identity_verified", owned)
	if !owned {
		return report, errors.New("scheduler_fixture_identity_unverified")
	}
	_, e = run(tool, "/Run", "/TN", task)
	executed := e == nil && awaitSchedulerReceipt(receipt, target)
	record("native_go_entry_executed", executed)
	report["pass"] = registered && owned && executed
	return report, nil
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
