package devtools

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"encoding/xml"
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/update"
	"os"
	"os/user"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"unicode/utf16"
)

func TestSchedulerDocumentsKeepUniqueIdentityAndPathData(t *testing.T) {
	fixture := `C:\Users\native test\한국 $ dollar ` + "`" + ` tick\host.exe`
	receipt := `C:\Users\native test\receipt.json`
	sid := "S-1-5-21-123-456-789-1000"
	document := fixtureWindowsTask("synthetic-private-id", fixture, receipt, sid)
	if !ownedFixtureWindowsTask(document, "synthetic-private-id", fixture, receipt, sid) {
		t.Fatal("owned native task rejected")
	}
	withoutDefault := bytes.Replace(document, []byte("<RunLevel>LeastPrivilege</RunLevel>"), nil, 1)
	if !ownedFixtureWindowsTask(withoutDefault, "synthetic-private-id", fixture, receipt, sid) {
		t.Fatal("documented omitted least-privilege default rejected")
	}
	explicitEmpty := bytes.Replace(document, []byte("<RunLevel>LeastPrivilege</RunLevel>"), []byte("<RunLevel/>"), 1)
	if ownedFixtureWindowsTask(explicitEmpty, "synthetic-private-id", fixture, receipt, sid) {
		t.Fatal("explicit empty RunLevel treated as default")
	}
	if strings.Index(string(document), "<Repetition>") > strings.Index(string(document), "<UserId>") {
		t.Fatal("base trigger repetition must precede logon-specific fields")
	}
	for _, changed := range []string{strings.Replace(string(document), "LeastPrivilege", "HighestAvailable", 1), strings.Replace(string(document), sid, "S-1-5-18", 1), strings.Replace(string(document), "synthetic-private-id", "another-task", 1), strings.Replace(string(document), "--scheduler-receipt", "--malicious", 1), strings.Replace(string(document), "PT24H", "PT48H", 1), strings.Replace(string(document), "PT5M", "PT1M", 1), strings.Replace(string(document), "<Enabled>true</Enabled>", "<Enabled>false</Enabled>", 1)} {
		if ownedFixtureWindowsTask([]byte(changed), "synthetic-private-id", fixture, receipt, sid) {
			t.Fatal("foreign scheduler task accepted")
		}
	}
	utf16Document := strings.Replace(string(document), `encoding="UTF-8"`, `encoding="UTF-16"`, 1)
	units := utf16.Encode([]rune(utf16Document))
	raw := []byte{0xff, 0xfe}
	for _, unit := range units {
		var b [2]byte
		binary.LittleEndian.PutUint16(b[:], unit)
		raw = append(raw, b[:]...)
	}
	if !ownedFixtureWindowsTask(raw, "synthetic-private-id", fixture, receipt, sid) {
		t.Fatal("native UTF16 task query rejected")
	}
	mac := fixtureLaunchAgent("com.opensocrates.acceptance.synthetic", `/private/한국 $ dollar `+"`"+` tick/host`, "/private/receipt.json", "/private/work")
	decoder := xml.NewDecoder(bytes.NewReader(mac))
	for {
		_, e := decoder.Token()
		if e != nil {
			if !strings.Contains(e.Error(), "EOF") {
				t.Fatal("LaunchAgent XML invalid")
			}
			break
		}
	}
	if bytes.Contains(mac, []byte("com.opensocrates.auto-update")) {
		t.Fatal("fixture touched production identity")
	}
}

func TestSchedulerRegistrationDiagnosticsAreBoundedAndContentFree(t *testing.T) {
	raw := []byte("ERROR: (2,198):UserId: S-1-5-21-123-456-789-1000 C:\\private\\fixture.xml\n")
	result := platform.Result{ExitCode: int(int64(0x80041318)), Stderr: raw}
	diagnostic := schedulerRegistrationDiagnostic(result, errors.New("synthetic_failure"))
	if diagnostic["hresult"] != "0x80041318" || diagnostic["known_error_class"] != "xml_value_invalid" || diagnostic["xml_line"] != 2 || diagnostic["xml_column"] != 198 || diagnostic["stderr_len"] != len(raw) {
		t.Fatal("bounded scheduler error classification missing")
	}
	encoded, e := json.Marshal(diagnostic)
	if e != nil {
		t.Fatal(e)
	}
	for _, private := range []string{"S-1-5-21", "C:\\private", "fixture.xml", "synthetic_failure", "ERROR:"} {
		if bytes.Contains(encoded, []byte(private)) {
			t.Fatal("raw account/path/error data leaked into scheduler evidence")
		}
	}
	denied := schedulerRegistrationDiagnostic(platform.Result{ExitCode: int(int64(0x80070005))}, errors.New("synthetic_failure"))
	if denied["known_error_class"] != "access_denied" {
		t.Fatal("access error misclassified")
	}
}

func TestSchedulerFixtureUsesNativeTaskImportEncoding(t *testing.T) {
	id := "synthetic-private-id"
	fixture := `C:\Users\native test\한국 $ dollar ` + "`" + ` tick\host.exe`
	receipt := `C:\Users\native test\receipt.json`
	sid := "S-1-5-21-123-456-789-1000"
	canonical := fixtureWindowsTask(id, fixture, receipt, sid)
	before := append([]byte(nil), canonical...)
	transport, e := update.EncodeTaskImportXML(canonical)
	if e != nil {
		t.Fatal(e)
	}
	if !bytes.HasPrefix(transport, []byte{0xff, 0xfe}) {
		t.Fatal("native import BOM missing")
	}
	decoded := schedulerWindowsText(transport)
	if !bytes.HasPrefix(decoded, []byte(`<?xml version="1.0" encoding="UTF-16"?>`)) {
		t.Fatal("task import declaration mismatches transport encoding")
	}
	if !bytes.Equal(decoded, bytes.Replace(canonical, []byte(`encoding="UTF-8"`), []byte(`encoding="UTF-16"`), 1)) {
		t.Fatal("task import changed canonical content")
	}
	if !bytes.Equal(canonical, before) || !ownedFixtureWindowsTask(transport, id, fixture, receipt, sid) {
		t.Fatal("native import weakened canonical ownership")
	}
	for _, bad := range [][]byte{[]byte("<Task>"), {0xff, 0xfe, 0xff}, []byte(`<?xml version="1.0" encoding="UTF-16"?><Task/>`)} {
		if _, e := update.EncodeTaskImportXML(bad); e == nil {
			t.Fatal("invalid canonical task source accepted")
		}
	}
}
func TestSchedulerCleanupRequiresProvenAbsence(t *testing.T) {
	if !schedulerTaskAbsent([]byte(`"\OtherTask","ready","never"`+"\n"), "OpenSocratesAcceptance-private") {
		t.Fatal("unrelated native task prevents proven absence")
	}
	if schedulerTaskAbsent([]byte(`"\OpenSocratesAcceptance-private","ready","never"`+"\n"), "OpenSocratesAcceptance-private") {
		t.Fatal("present task treated absent")
	}
	if schedulerTaskAbsent([]byte(`"malformed`), "OpenSocratesAcceptance-private") {
		t.Fatal("unknown query failure treated absent")
	}
}
func TestSchedulerReceiptOwnershipAndClosedArgs(t *testing.T) {
	root := filepath.Join(t.TempDir(), "opensocrates-native-scheduler-synthetic")
	if e := platform.Mkdir(root); e != nil {
		t.Fatal(e)
	}
	receipt := filepath.Join(root, "receipt.json")
	if AcceptanceHostFixture([]string{"--scheduler-receipt", receipt, "extra"}, os.Stdout) == 0 {
		t.Fatal("unknown receipt args accepted")
	}
	if schedulerReceipt(filepath.Join(root, "foreign.json")) == 0 {
		t.Fatal("foreign filename accepted")
	}
	if nativeAcceptanceTarget() == "unsupported" {
		if schedulerReceipt(receipt) == 0 {
			t.Fatal("unsupported native platform claimed")
		}
		return
	}
	if schedulerReceipt(receipt) != 0 || !readSchedulerReceipt(receipt, nativeAcceptanceTarget()) {
		t.Fatal("native owned receipt missing")
	}
	if schedulerReceipt(receipt) == 0 {
		t.Fatal("receipt overwritten")
	}
}

func TestSchedulerQueryProjectionOmitsPersonalDataAndShowsApprovedDefaults(t *testing.T) {
	canonical := fixtureWindowsTask("synthetic-private-id", `C:\private\host.exe`, `C:\private\receipt.json`, "S-1-5-21-123-456-789-1000")
	exported := strings.Replace(string(canonical), "<RegistrationInfo>", `<RegistrationInfo><Author>private-account-name</Author><URI>\PrivateTaskName</URI>`, 1)
	exported = strings.Replace(exported, "<Settings>", `<Settings><Priority>7</Priority><AllowHardTerminate>true</AllowHardTerminate><IdleSettings><Duration>PT10M</Duration><WaitTimeout>PT1H</WaitTimeout></IdleSettings><UnknownPrivateTag>private-value</UnknownPrivateTag>`, 1)
	projection := schedulerQueryProjection([]byte(exported), canonical)
	settings := projection["approved_settings"].(map[string]any)
	if settings["Task/Settings/Priority"] != 7 || settings["Task/Settings/AllowHardTerminate"] != true || settings["Task/Settings/IdleSettings/Duration"] != "PT10M" || projection["xml_parsed"] != true {
		t.Fatal("approved OS defaults not projected")
	}
	encoded, e := json.Marshal(projection)
	if e != nil {
		t.Fatal(e)
	}
	for _, private := range []string{"private-account-name", "PrivateTaskName", "S-1-5-21", "C:\\private", "UnknownPrivateTag", "private-value", "synthetic-private-id"} {
		if bytes.Contains(encoded, []byte(private)) {
			t.Fatal("personal or unapproved query metadata leaked")
		}
	}
	equivalent := bytes.Replace(canonical, []byte("PT24H"), []byte("P1D"), 1)
	if !ownedFixtureWindowsTask(equivalent, "synthetic-private-id", `C:\private\host.exe`, `C:\private\receipt.json`, "S-1-5-21-123-456-789-1000") {
		t.Fatal("exact 24-hour duration reserialization rejected")
	}
}

func TestSchedulerPriorFixtureCleanupRejectsForeignIdentityActionAndRoot(t *testing.T) {
	id := "9661c9a0b58687fe5b565db800e91073"
	sid := "S-1-5-21-123-456-789-1000"
	root := filepath.Join(t.TempDir(), "opensocrates-native-scheduler-"+id+"-1234")
	fixture := filepath.Join(root, "native-scheduler-entry.exe")
	receipt := filepath.Join(root, "receipt.json")
	doc := fixtureWindowsTask(id, fixture, receipt, sid)
	actualRoot, actualFixture, ok := schedulerCleanupDefinition(doc, id, sid)
	if !ok || actualRoot != root || actualFixture != fixture {
		t.Fatal("exact retained fixture rejected")
	}
	for _, changedID := range []string{"com.opensocrates.auto-update", "9661c9a0b58687fe5b565db800e91074", strings.ToUpper(id), "", id + "/../"} {
		if _, _, ok := schedulerCleanupDefinition(doc, changedID, sid); ok {
			t.Fatal("foreign fixture identity accepted")
		}
	}
	for _, changed := range [][]byte{
		bytes.Replace(doc, []byte("--scheduler-receipt"), []byte("--foreign-command"), 1),
		fixtureWindowsTask(id, filepath.Join(t.TempDir(), "native-scheduler-entry.exe"), receipt, sid),
		fixtureWindowsTask(id, filepath.Join(filepath.Dir(root), "opensocrates-native-scheduler-"+id+"-", "native-scheduler-entry.exe"), receipt, sid),
		bytes.Replace(doc, []byte("<Settings>"), []byte("<Settings><UnknownForeignSetting>true</UnknownForeignSetting>"), 1),
		bytes.Replace(doc, []byte("<Actions Context=\"User\">"), []byte("<Actions Context=\"User\"><ComHandler><ClassId>foreign</ClassId></ComHandler>"), 1),
		bytes.Replace(doc, []byte("<Triggers>"), []byte("<Triggers><BootTrigger><Enabled>true</Enabled></BootTrigger>"), 1),
		bytes.Replace(doc, []byte("<Settings>"), []byte("<Settings><Hidden>true</Hidden>"), 1),
	} {
		if _, _, ok := schedulerCleanupDefinition(changed, id, sid); ok {
			t.Fatal("changed or foreign fixture definition accepted")
		}
	}
	if _, _, ok := schedulerCleanupDefinition(doc, id, "S-1-5-18"); ok {
		t.Fatal("foreign owner accepted")
	}
}

func TestSchedulerCapturedExportRestoreRetainsOSDefaultsAndRejectsChanges(t *testing.T) {
	id := "9661c9a0b58687fe5b565db800e91073"
	sid := "S-1-5-21-123-456-789-1000"
	fixture, receipt := `C:\private\native-scheduler-entry.exe`, `C:\private\receipt.json`
	exported := fixtureWindowsTask(id, fixture, receipt, sid)
	exported = bytes.Replace(exported, []byte("<RunLevel>LeastPrivilege</RunLevel>"), nil, 1)
	// This is the actual exported subset: both trigger and task Enabled=true
	// disappear along with default least privilege and other schema defaults.
	exported = bytes.ReplaceAll(exported, []byte("<Enabled>true</Enabled>"), nil)
	exported = bytes.Replace(exported, []byte("<AllowStartOnDemand>true</AllowStartOnDemand>"), nil, 1)
	exported = bytes.Replace(exported, []byte("<StopAtDurationEnd>false</StopAtDurationEnd>"), nil, 1)
	exported = bytes.Replace(exported, []byte("PT24H"), []byte("P1D"), 1)
	exported = bytes.Replace(exported, []byte("<Settings>"), []byte("<Settings><UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine><IdleSettings><StopOnIdleEnd>true</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>"), 1)
	exported = bytes.Replace(exported, []byte("<RegistrationInfo>"), []byte(`<RegistrationInfo><URI>\OpenSocratesAcceptance-`+id+`</URI>`), 1)
	if !ownedFixtureWindowsTask(exported, id, fixture, receipt, sid) {
		t.Fatal("observed native task defaults rejected")
	}
	for _, disabled := range []string{"<Enabled>false</Enabled>", "<Enabled/>"} {
		changed := bytes.Replace(exported, []byte("<LogonTrigger>"), []byte("<LogonTrigger>"+disabled), 1)
		if ownedFixtureWindowsTask(changed, id, fixture, receipt, sid) {
			t.Fatal("explicit disabled or empty trigger Enabled accepted as default")
		}
	}
	transport, e := update.EncodeTaskImportXML(exported)
	if e != nil {
		t.Fatal(e)
	}
	if !update.TaskDocumentMatches(transport, exported, fixture) {
		t.Fatal("captured restore changed the complete task tree")
	}
	foreign := bytes.Replace(exported, []byte("<Settings>"), []byte("<Settings><UnknownForeignSetting>true</UnknownForeignSetting>"), 1)
	if update.TaskDocumentMatches(foreign, exported, fixture) || ownedFixtureWindowsTask(foreign, id, fixture, receipt, sid) {
		t.Fatal("unknown foreign policy treated as equivalent or owned")
	}
	changed := bytes.Replace(exported, []byte("<RestartOnIdle>false"), []byte("<RestartOnIdle>true"), 1)
	if update.TaskDocumentMatches(changed, exported, fixture) || ownedFixtureWindowsTask(changed, id, fixture, receipt, sid) {
		t.Fatal("modified captured OS default accepted")
	}
}

func TestSchedulerFixtureIdentityPreservesModifiedOrForeignFiles(t *testing.T) {
	id := "9661c9a0b58687fe5b565db800e91073"
	setup := func(t *testing.T) (string, []byte) {
		t.Helper()
		root, e := platform.MkdirTemp("", "opensocrates-native-scheduler-"+id+"-")
		if e != nil {
			t.Fatal(e)
		}
		t.Cleanup(func() { _ = platform.RemoveTree(root) })
		if e = platform.ExclusiveWrite(filepath.Join(root, "native-scheduler-entry.exe"), []byte("synthetic-native-go-fixture-bytes"), 0755); e != nil {
			t.Fatal(e)
		}
		identity, e := createSchedulerFixtureIdentity(root, id, "native-scheduler-entry.exe")
		if e != nil {
			t.Fatal(e)
		}
		return root, identity
	}
	t.Run("exact inventory and durable recorded files", func(t *testing.T) {
		root, identity := setup(t)
		if ok, e := verifySchedulerFixtureFiles(root, id, "native-scheduler-entry.exe", identity); e != nil || !ok {
			t.Fatal("exact copied executable identity rejected")
		}
		document := fixtureWindowsTask(id, filepath.Join(root, "native-scheduler-entry.exe"), filepath.Join(root, "receipt.json"), "S-1-5-21-123-456-789-1000")
		if e := platform.ExclusiveWrite(filepath.Join(root, "fixture-task.xml"), document, 0600); e != nil {
			t.Fatal(e)
		}
		updated, e := recordSchedulerFixtureFile(root, identity, "fixture-task.xml")
		if e != nil {
			t.Fatal(e)
		}
		if ok, e := verifySchedulerFixtureFiles(root, id, "native-scheduler-entry.exe", updated); e != nil || !ok {
			t.Fatal("durable closed generated file inventory rejected")
		}
		if e = platform.AtomicWrite(filepath.Join(root, "fixture-task.xml"), bytes.Replace(document, []byte("PT24H"), []byte("PT48H"), 1), 0600); e != nil {
			t.Fatal(e)
		}
		if ok, e := verifySchedulerFixtureFiles(root, id, "native-scheduler-entry.exe", nil); e == nil || ok {
			t.Fatal("modified generated definition eligible for deletion")
		}
	})
	for _, name := range []string{"executable", "identity", "extra file"} {
		t.Run(name, func(t *testing.T) {
			root, identity := setup(t)
			switch name {
			case "executable":
				if e := platform.AtomicWrite(filepath.Join(root, "native-scheduler-entry.exe"), []byte("modified-foreign-bytes"), 0755); e != nil {
					t.Fatal(e)
				}
			case "identity":
				changed := bytes.Replace(identity, []byte(id), []byte("9661c9a0b58687fe5b565db800e91074"), 1)
				if e := platform.AtomicWrite(filepath.Join(root, "fixture-identity.json"), changed, 0600); e != nil {
					t.Fatal(e)
				}
			case "extra file":
				if e := platform.ExclusiveWrite(filepath.Join(root, "foreign.txt"), []byte("preserve this"), 0600); e != nil {
					t.Fatal(e)
				}
			}
			if ok, e := verifySchedulerFixtureFiles(root, id, "native-scheduler-entry.exe", nil); e == nil || ok {
				t.Fatal("modified or foreign files eligible for deletion")
			}
			if _, e := os.Stat(root); e != nil {
				t.Fatal("verification removed retained files")
			}
		})
	}
	t.Run("legacy fixture has no removal authority", func(t *testing.T) {
		root, e := platform.MkdirTemp("", "opensocrates-native-scheduler-"+id+"-")
		if e != nil {
			t.Fatal(e)
		}
		t.Cleanup(func() { _ = platform.RemoveTree(root) })
		if e = platform.ExclusiveWrite(filepath.Join(root, "native-scheduler-entry.exe"), []byte("legacy-unknown-bytes"), 0755); e != nil {
			t.Fatal(e)
		}
		if ok, e := verifySchedulerFixtureFiles(root, id, "native-scheduler-entry.exe", nil); e != nil || ok {
			t.Fatal("legacy fixture gained unverified file deletion authority")
		}
	})
}

func TestSchedulerIdentityDiagnosticShowsOnlyBoundedComparisons(t *testing.T) {
	id, sid := "9661c9a0b58687fe5b565db800e91073", "S-1-5-21-123-456-789-1000"
	fixture, receipt := `C:\private\native-scheduler-entry.exe`, `C:\private\receipt.json`
	doc := fixtureWindowsTask(id, fixture, receipt, sid)
	doc = bytes.ReplaceAll(doc, []byte(`id="User"`), []byte(`id="Author"`))
	doc = bytes.ReplaceAll(doc, []byte(`Context="User"`), []byte(`Context="Author"`))
	diagnostic := fixtureTaskIdentityDiagnostic(doc, id, fixture, receipt, sid)
	if diagnostic["principal_id_enum"] != "Author" || diagnostic["action_context_enum"] != "Author" || diagnostic["context_reference_match"] != true || diagnostic["full_closed_policy_match"] != false || diagnostic["current_sid_match"] != true {
		t.Fatal("identity mismatch not distinguished by bounded comparisons")
	}
	encoded, e := json.Marshal(diagnostic)
	if e != nil {
		t.Fatal(e)
	}
	for _, private := range []string{id, sid, "C:\\private", "native-scheduler-entry.exe", "receipt.json", "--scheduler-receipt"} {
		if bytes.Contains(encoded, []byte(private)) {
			t.Fatal("private identity data recorded")
		}
	}
}

func TestSchedulerNativeWindowsAccountAliasPreservesCapturedRoundtrip(t *testing.T) {
	if runtime.GOOS != "windows" {
		t.Skip("native Windows account resolver required")
	}
	current, e := user.Current()
	if e != nil || !strings.HasPrefix(current.Uid, "S-1-") || current.Username == "" {
		t.Fatal("native current account identity unavailable")
	}
	id := "9661c9a0b58687fe5b565db800e91073"
	fixture, receipt := `C:\private\native-scheduler-entry.exe`, `C:\private\receipt.json`
	canonical := fixtureWindowsTask(id, fixture, receipt, current.Uid)
	// Only the first UserId belongs to the logon trigger. The Principal keeps
	// its SID, exactly as observed in the native Task Scheduler export.
	aliasExport := bytes.Replace(canonical, []byte("<UserId>"+current.Uid+"</UserId>"), []byte("<UserId>"+schedulerXMLText(current.Username)+"</UserId>"), 1)
	if !ownedFixtureWindowsTask(aliasExport, id, fixture, receipt, current.Uid) {
		t.Fatal("OS-resolved same-account trigger rejected")
	}
	transport, e := update.EncodeTaskImportXML(aliasExport)
	if e != nil || !update.TaskDocumentMatches(transport, aliasExport, fixture) {
		t.Fatal("captured account-alias export changed during restore transport")
	}
	if update.TaskDocumentMatches(transport, canonical, fixture) {
		t.Fatal("captured-before account field silently rewritten")
	}
	foreign := bytes.Replace(aliasExport, []byte(schedulerXMLText(current.Username)), []byte("OpenSocrates-nonexistent-fixture-account-9661c9a0"), 1)
	if ownedFixtureWindowsTask(foreign, id, fixture, receipt, current.Uid) {
		t.Fatal("unresolved account alias inherited current-user ownership")
	}
	if update.TaskUserIdentityMatches(current.Username, "S-1-5-18") {
		t.Fatal("same-name lookup accepted a different SID")
	}
}
