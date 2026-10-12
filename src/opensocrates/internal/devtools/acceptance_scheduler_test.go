package devtools

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"encoding/xml"
	"errors"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"os"
	"path/filepath"
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
