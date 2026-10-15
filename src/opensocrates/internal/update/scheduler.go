package update

import (
	"bytes"
	"context"
	"encoding/binary"
	"encoding/csv"
	"encoding/json"
	"encoding/xml"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/diagnostics"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/registration"
	"io"
	"os"
	"os/user"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"
	"unicode/utf16"
	"unicode/utf8"
)

const SchedulerLabel = "com.opensocrates.auto-update"
const TaskName = "OpenSocrates Native Stable Update"

// SchedulerAdapter participates in the same journal/rollback as host mutations.
// Documents are local recovery state; paths are never copied into receipts.
type SchedulerAdapter struct {
	OS, Home, ManagerPath, StateDir string
	Command                         func(context.Context, string, ...string) ([]byte, error)
}

func NewSchedulerAdapter(goos, home, managerPath, stateDir string) *SchedulerAdapter {
	return &SchedulerAdapter{OS: goos, Home: home, ManagerPath: managerPath, StateDir: stateDir}
}
func (a *SchedulerAdapter) Root() string {
	if a.OS == "darwin" {
		return filepath.Join(a.Home, "Library", "LaunchAgents", SchedulerLabel+".plist")
	}
	return TaskName
}
func escape(s string) string {
	var b bytes.Buffer
	_ = xml.EscapeText(&b, []byte(s))
	return b.String()
}
func LaunchAgent(manager string) ([]byte, error) {
	if !filepath.IsAbs(manager) || strings.ContainsRune(manager, 0) {
		return nil, closed(diagnostics.Verification, "scheduler")
	}
	return []byte(`<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>` + SchedulerLabel + `</string>
<key>ProgramArguments</key><array><string>` + escape(manager) + `</string><string>auto-update</string><string>run</string><string>--scheduled</string><string>--login-delay</string><string>300</string></array>
<key>RunAtLoad</key><true/><key>StartInterval</key><integer>86400</integer>
<key>ProcessType</key><string>Background</string><key>StandardOutPath</key><string>/dev/null</string><key>StandardErrorPath</key><string>/dev/null</string>
</dict></plist>
`), nil
}
func WindowsTask(manager, sid string) ([]byte, error) {
	if !(filepath.IsAbs(manager) || len(manager) > 3 && manager[1] == ':' && (manager[2] == 92 || manager[2] == '/')) || strings.ContainsAny(manager, "\x00\r\n") || !strings.HasPrefix(sid, "S-1-") {
		return nil, closed(diagnostics.Verification, "scheduler")
	}
	return []byte(`<?xml version="1.0" encoding="UTF-8"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
<RegistrationInfo><Description>OpenSocrates native stable updater; owned by opensocrates-native</Description></RegistrationInfo>
<Triggers><LogonTrigger><Enabled>true</Enabled><Repetition><Interval>PT24H</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition><UserId>` + escape(sid) + `</UserId><Delay>PT5M</Delay></LogonTrigger></Triggers>
<Principals><Principal id="User"><UserId>` + escape(sid) + `</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable><Enabled>true</Enabled><UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine><ExecutionTimeLimit>PT10M</ExecutionTimeLimit></Settings>
<Actions Context="User"><Exec><Command>` + escape(manager) + `</Command><Arguments>auto-update run --scheduled</Arguments></Exec></Actions></Task>
`), nil
}
func (a *SchedulerAdapter) command(ctx context.Context, exe string, args ...string) ([]byte, error) {
	if a.Command != nil {
		return a.Command(ctx, exe, args...)
	}
	name := "launchctl"
	if a.OS == "windows" {
		name = "schtasks.exe"
	}
	trusted, err := platform.SystemExecutable(name)
	if err != nil {
		return nil, err
	}
	exe = trusted
	ctx, cancel := context.WithTimeout(ctx, 20*time.Second)
	defer cancel()
	result, err := platform.Run(ctx, exe, args, platform.RunOptions{OutputLimit: 1 << 20})
	if err != nil {
		return nil, closed(diagnostics.Activation, "scheduler")
	}
	return result.Stdout, nil
}

func (a *SchedulerAdapter) tool() string {
	if a.OS == "darwin" {
		return "/bin/launchctl"
	}
	return `C:\Windows\System32\schtasks.exe`
}
func (a *SchedulerAdapter) domain() string { return "gui/" + strconv.Itoa(os.Getuid()) }
func (a *SchedulerAdapter) Inspect(ctx context.Context, root string) (registration.State, error) {
	s := registration.State{Root: root, Data: map[string]string{}}
	if root != a.Root() {
		return s, closed(diagnostics.Verification, "scheduler_ownership")
	}
	if a.OS == "darwin" {
		b, e := platform.ReadOwnedFile(root, 1<<20)
		if e != nil {
			if _, stat := os.Lstat(root); os.IsNotExist(stat) {
				return s, nil
			}
			return s, e
		}
		if !ownedPlist(b, a.ManagerPath) {
			return s, closed(diagnostics.Verification, "scheduler_ownership")
		}
		s.Installed = true
		s.Data["document"] = string(b)
		_, e = a.command(ctx, a.tool(), "print", a.domain()+"/"+SchedulerLabel)
		if e != nil {
			domain, err := a.command(ctx, a.tool(), "print", a.domain())
			if err != nil {
				return s, err
			}
			for _, line := range strings.Split(string(domain), "\n") {
				fields := strings.Fields(line)
				if len(fields) > 0 && fields[len(fields)-1] == SchedulerLabel {
					return s, closed(diagnostics.HostUnavailable, "scheduler_state")
				}
			}
		}
		s.Registered = e == nil
		s.Enabled = s.Registered
		return s, nil
	}
	if a.OS != "windows" {
		return s, closed(diagnostics.Unsupported, "scheduler")
	}
	all, e := a.command(ctx, a.tool(), "/Query", "/FO", "CSV", "/NH")
	if e != nil {
		return s, e
	}
	rows, e := csv.NewReader(strings.NewReader(string(decodeWindows(all)))).ReadAll()
	if e != nil {
		return s, closed(diagnostics.Verification, "scheduler")
	}
	found := false
	for _, row := range rows {
		if len(row) > 0 && (row[0] == TaskName || row[0] == "\\"+TaskName) {
			found = true
		}
	}
	if !found {
		return s, nil
	}
	b, e := a.command(ctx, a.tool(), "/Query", "/TN", TaskName, "/XML")
	if e != nil {
		return s, e
	} // Unknown access failure is never interpreted as absence.
	b, e = normalizeTaskXML(b)
	if e != nil {
		return s, e
	}
	if !ownedTask(b, a.ManagerPath) {
		return s, closed(diagnostics.Verification, "scheduler_ownership")
	}
	u, err := user.Current()
	if err != nil || taskUser(b) != u.Uid {
		return s, closed(diagnostics.Permission, "scheduler_owner")
	}
	s.Installed = true
	s.Registered = true
	s.Enabled = true
	s.Data["document"] = string(b)
	return s, nil
}
func (a *SchedulerAdapter) Replace(ctx context.Context, before, after registration.State) error {
	actual, e := a.Inspect(ctx, before.Root)
	if e != nil {
		return e
	}
	if actual.Installed == after.Installed && actual.Registered == after.Registered && a.knownDocument(actual.Data["document"], after.Data["document"]) {
		return nil
	}
	// A journaled command may have stopped the task or replaced its document
	// before interruption. Only either known document (or an absent identity)
	// can participate in recovery; changed foreign documents always conflict.
	if actual.Installed && !a.knownDocument(actual.Data["document"], before.Data["document"]) && !a.knownDocument(actual.Data["document"], after.Data["document"]) {
		return closed(diagnostics.Verification, "scheduler_conflict")
	}
	before = actual
	if a.OS == "darwin" {
		if before.Registered {
			if _, e = a.command(ctx, a.tool(), "bootout", a.domain()+"/"+SchedulerLabel); e != nil {
				return e
			}
		}
		if !after.Installed {
			if before.Installed {
				return platform.Remove(after.Root)
			}
			return nil
		}
		doc := []byte(after.Data["document"])
		if !ownedPlist(doc, a.ManagerPath) {
			return closed(diagnostics.Verification, "scheduler_ownership")
		}
		if e = platform.Mkdir(filepath.Dir(after.Root)); e != nil {
			return e
		}
		if e = platform.AtomicWrite(after.Root, doc, 0600); e != nil {
			return e
		}
		if after.Registered {
			_, e = a.command(ctx, a.tool(), "bootstrap", a.domain(), after.Root)
		}
		return e
	}
	if !after.Installed {
		if !before.Installed {
			return nil
		}
		_, e = a.command(ctx, a.tool(), "/Delete", "/TN", TaskName, "/F")
		return e
	}
	doc := []byte(after.Data["document"])
	if !ownedTask(doc, a.ManagerPath) {
		return closed(diagnostics.Verification, "scheduler_ownership")
	}
	if e = platform.Mkdir(a.StateDir); e != nil {
		return e
	}
	task := filepath.Join(a.StateDir, "scheduled-task.xml")
	importXML, err := EncodeTaskImportXML(doc)
	if err != nil {
		return err
	}
	if e = platform.AtomicWrite(task, importXML, 0600); e != nil {
		return e
	}
	if before.Installed {
		if _, e = a.command(ctx, a.tool(), "/Delete", "/TN", TaskName, "/F"); e != nil {
			return e
		}
	}
	_, e = a.command(ctx, a.tool(), "/Create", "/TN", TaskName, "/XML", task)
	return e
}
func (a *SchedulerAdapter) Verify(ctx context.Context, want registration.State) error {
	got, e := a.Inspect(ctx, want.Root)
	if e != nil {
		return e
	}
	if got.Installed != want.Installed || got.Registered != want.Registered {
		return closed(diagnostics.Activation, "scheduler_verify")
	}
	if want.Installed && !a.knownDocument(got.Data["document"], want.Data["document"]) {
		return closed(diagnostics.Verification, "scheduler_verify")
	}
	return nil
}
func PrepareMigration(ctx context.Context, a *SchedulerAdapter, enabled bool) (*registration.Change, error) {
	before, e := a.Inspect(ctx, a.Root())
	if e != nil {
		return nil, e
	}
	after := registration.State{Root: a.Root(), Installed: enabled, Registered: enabled, Enabled: enabled, Version: "1.6.0", Data: map[string]string{}}
	if enabled {
		var doc []byte
		if a.OS == "darwin" {
			doc, e = LaunchAgent(a.ManagerPath)
		} else {
			u, err := user.Current()
			if err != nil {
				return nil, closed(diagnostics.Permission, "scheduler")
			}
			doc, e = WindowsTask(a.ManagerPath, u.Uid)
		}
		if e != nil {
			return nil, e
		}
		after.Data["document"] = string(doc)
	}
	return &registration.Change{Host: "scheduler", Before: before, After: after}, nil
}

// Recognize only the exact owned label and command identities. Legacy npm
// scheduling is preserved as recovery data; unrelated npm packages stay put.
func ownedPlist(b []byte, manager string) bool {
	d := xml.NewDecoder(bytes.NewReader(b))
	var label string
	var args []string
	key := ""
	array := false
	for {
		tok, e := d.Token()
		if e != nil {
			if e != io.EOF {
				return false
			}
			break
		}
		switch t := tok.(type) {
		case xml.StartElement:
			switch t.Name.Local {
			case "key":
				if d.DecodeElement(&key, &t) != nil {
					return false
				}
			case "array":
				if key == "ProgramArguments" {
					array = true
				}
			case "string":
				var val string
				if d.DecodeElement(&val, &t) != nil {
					return false
				}
				if array {
					args = append(args, val)
				} else if key == "Label" {
					label = val
				}
			}
		case xml.EndElement:
			if t.Name.Local == "array" {
				array = false
			}
		}
	}
	if label != SchedulerLabel {
		return false
	}
	if len(args) >= 3 && args[0] == manager && args[1] == "auto-update" && args[2] == "run" {
		return true
	}
	return len(args) == 5 && filepath.Base(args[0]) == "npx" && args[1] == "--yes" && (args[2] == "opensocrates@latest" || args[2] == "opensocrates@next") && args[3] == "auto-update" && args[4] == "run"
}
func ownedTask(b []byte, manager string) bool {
	return ownedTaskWithResolver(b, manager, ResolveAccountSID)
}
func ownedTaskWithResolver(b []byte, manager string, resolver AccountSIDResolver) bool {
	var t struct {
		Description string `xml:"RegistrationInfo>Description"`
		Actions     []struct {
			Command   string `xml:"Command"`
			Arguments string `xml:"Arguments"`
		} `xml:"Actions>Exec"`
		UserID             string  `xml:"Principals>Principal>UserId"`
		TriggerUserID      string  `xml:"Triggers>LogonTrigger>UserId"`
		LogonType          string  `xml:"Principals>Principal>LogonType"`
		RunLevel           *string `xml:"Principals>Principal>RunLevel"`
		TriggerEnabled     *bool   `xml:"Triggers>LogonTrigger>Enabled"`
		SettingsEnabled    *bool   `xml:"Settings>Enabled"`
		AllowStartOnDemand *bool   `xml:"Settings>AllowStartOnDemand"`
		StopAtDurationEnd  *bool   `xml:"Triggers>LogonTrigger>Repetition>StopAtDurationEnd"`
		Delay              string  `xml:"Triggers>LogonTrigger>Delay"`
		Interval           string  `xml:"Triggers>LogonTrigger>Repetition>Interval"`
		Instances          string  `xml:"Settings>MultipleInstancesPolicy"`
	}
	if xml.Unmarshal(b, &t) != nil || len(t.Actions) != 1 || t.Actions[0].Command != manager || t.Actions[0].Arguments != "auto-update run --scheduled" || t.LogonType != "InteractiveToken" || (t.RunLevel != nil && *t.RunLevel != "LeastPrivilege") || (t.TriggerEnabled != nil && !*t.TriggerEnabled) || (t.SettingsEnabled != nil && !*t.SettingsEnabled) || (t.AllowStartOnDemand != nil && !*t.AllowStartOnDemand) || (t.StopAtDurationEnd != nil && *t.StopAtDurationEnd) || !strings.Contains(t.Description, "owned by "+Owner) || taskDurationValue("Task/Triggers/LogonTrigger/Delay", t.Delay) != "PT5M" || taskDurationValue("Task/Triggers/LogonTrigger/Repetition/Interval", t.Interval) != "PT24H" || t.Instances != "IgnoreNew" || !strings.HasPrefix(t.UserID, "S-1-") || !TaskUserIdentityMatchesWithResolver(t.TriggerUserID, t.UserID, resolver) {
		return false
	}
	d := xml.NewDecoder(bytes.NewReader(b))
	for {
		token, err := d.Token()
		if err != nil {
			break
		}
		if x, ok := token.(xml.StartElement); ok && (x.Name.Local == "ComHandler" || x.Name.Local == "SendEmail" || x.Name.Local == "ShowMessage") {
			return false
		}
	}
	return true
}
func taskUser(b []byte) string {
	var t struct {
		ID string `xml:"Principals>Principal>UserId"`
	}
	if xml.Unmarshal(b, &t) != nil {
		return ""
	}
	return t.ID
}

// LoginWait is cancellation-aware; periodic jobs also wait to coalesce wakeups.
func LoginWait(ctx context.Context) error {
	timer := time.NewTimer(LoginDelay)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return closed(diagnostics.Activation, "cancelled")
	case <-timer.C:
		return nil
	}
}

func decodeWindows(b []byte) []byte {
	if len(b) >= 2 && b[0] == 255 && b[1] == 254 {
		u := make([]uint16, (len(b)-2)/2)
		for i := range u {
			u[i] = binary.LittleEndian.Uint16(b[2+i*2:])
		}
		return []byte(string(utf16.Decode(u)))
	}
	return b
}

// Configuration is consumed as one shared lifecycle plan: PolicyJSON is staged
// as an owner-checked file mutation, Registration is journaled before any OS
// scheduler change. Reboot recovery then restores policy and exact task together.
type Configuration struct {
	Registration registration.Change
	PolicyPath   string
	PolicyJSON   []byte
}

func (e Engine) PrepareConfiguration(ctx context.Context, enabled bool, a *SchedulerAdapter) (Configuration, error) {
	var c Configuration
	if e.OS != "darwin" || e.Arch != "arm64" {
		if e.OS != "windows" || (e.Arch != "amd64" && e.Arch != "arm64") {
			return c, closed(diagnostics.Unsupported, "scheduler")
		}
	}
	if enabled && ValidateProductionRoot(e.Repository.BootstrapRoot, e.now()) != nil {
		return c, closed(diagnostics.HostUnavailable, "trust_root")
	}
	change, err := PrepareMigration(ctx, a, enabled)
	if err != nil {
		return c, err
	}
	p, err := e.Policy()
	if err != nil {
		return c, err
	}
	p.Enabled = enabled
	p.Owner = Owner
	p.Channel = "stable"
	p.Hosts = []string{"codex"}
	p.NextCheck = e.now().Add(LoginDelay)
	b, err := json.Marshal(p)
	if err != nil {
		return c, closed(diagnostics.Verification, "policy")
	}
	return Configuration{Registration: *change, PolicyPath: filepath.Join(e.StateDir, "update-policy.json"), PolicyJSON: append(b, '\n')}, nil
}

const maxTaskXMLBytes = 1 << 20
const taskUTF8Declaration = `<?xml version="1.0" encoding="UTF-8"?>`
const taskUTF16Declaration = `<?xml version="1.0" encoding="UTF-16"?>`

// EncodeTaskImportXML is the native schtasks /XML file boundary. Ownership and
// registration policy are checked by the caller before this pure transform.
// Canonical recovery state stays UTF-8; the import file is UTF-16LE with a BOM
// and a matching declaration, including Unicode and supplementary characters.
func EncodeTaskImportXML(canonicalUTF8 []byte) ([]byte, error) {
	if err := validateCanonicalTaskXML(canonicalUTF8); err != nil {
		return nil, err
	}
	text := taskUTF16Declaration + string(canonicalUTF8[len(taskUTF8Declaration):])
	units := utf16.Encode([]rune(text))
	encoded := make([]byte, 2+len(units)*2)
	encoded[0], encoded[1] = 0xff, 0xfe
	for i, unit := range units {
		binary.LittleEndian.PutUint16(encoded[2+i*2:], unit)
	}
	return encoded, nil
}

func validateCanonicalTaskXML(document []byte) error {
	if len(document) > maxTaskXMLBytes || !utf8.Valid(document) || !bytes.HasPrefix(document, []byte(taskUTF8Declaration)) {
		return closed(diagnostics.Verification, "scheduler_xml")
	}
	decoder := xml.NewDecoder(bytes.NewReader(document))
	roots, depth := 0, 0
	for {
		token, err := decoder.Token()
		if err == io.EOF {
			break
		}
		if err != nil {
			return closed(diagnostics.Verification, "scheduler_xml")
		}
		switch value := token.(type) {
		case xml.StartElement:
			if depth == 0 {
				roots++
				if roots != 1 || value.Name.Local != "Task" || value.Name.Space != "http://schemas.microsoft.com/windows/2004/02/mit/task" {
					return closed(diagnostics.Verification, "scheduler_xml")
				}
			}
			depth++
		case xml.EndElement:
			depth--
		case xml.Directive:
			return closed(diagnostics.Verification, "scheduler_xml")
		case xml.CharData:
			if depth == 0 && len(bytes.TrimSpace(value)) != 0 {
				return closed(diagnostics.Verification, "scheduler_xml")
			}
		}
	}
	if roots != 1 || depth != 0 {
		return closed(diagnostics.Verification, "scheduler_xml")
	}
	return nil
}

// normalizeTaskXML decodes bounded Windows query output and normalizes only its
// encoding declaration. A malformed BOM, UTF-16 pair, or XML document fails
// closed before ownership inspection or recovery state capture.
func normalizeTaskXML(raw []byte) ([]byte, error) {
	if len(raw) > 2*maxTaskXMLBytes+2 {
		return nil, closed(diagnostics.Verification, "scheduler_xml")
	}
	var document []byte
	if len(raw) >= 2 && raw[0] == 0xff && raw[1] == 0xfe {
		if len(raw)%2 != 0 {
			return nil, closed(diagnostics.Verification, "scheduler_xml")
		}
		units := make([]uint16, (len(raw)-2)/2)
		for i := range units {
			units[i] = binary.LittleEndian.Uint16(raw[2+i*2:])
		}
		for i := 0; i < len(units); i++ {
			u := units[i]
			if u >= 0xd800 && u <= 0xdbff {
				if i+1 >= len(units) || units[i+1] < 0xdc00 || units[i+1] > 0xdfff {
					return nil, closed(diagnostics.Verification, "scheduler_xml")
				}
				i++
			} else if u >= 0xdc00 && u <= 0xdfff {
				return nil, closed(diagnostics.Verification, "scheduler_xml")
			}
		}
		document = []byte(string(utf16.Decode(units)))
		if !bytes.HasPrefix(document, []byte(taskUTF16Declaration)) {
			return nil, closed(diagnostics.Verification, "scheduler_xml")
		}
	} else {
		document = append([]byte(nil), raw...)
	}
	if bytes.HasPrefix(document, []byte{0xef, 0xbb, 0xbf}) {
		document = document[3:]
	}
	if bytes.HasPrefix(document, []byte(taskUTF16Declaration)) {
		document = []byte(taskUTF8Declaration + string(document[len(taskUTF16Declaration):]))
	}
	if err := validateCanonicalTaskXML(document); err != nil {
		return nil, err
	}
	return document, nil
}

func (a *SchedulerAdapter) knownDocument(actual, known string) bool {
	if actual == known {
		return true
	}
	if a.OS != "windows" {
		return false
	}
	return TaskDocumentMatches([]byte(actual), []byte(known), a.ManagerPath)
}

// TaskDocumentMatches permits OS representation/default expansion only for an
// exact definition produced by WindowsTask. Captured before-state remains an
// exact value match after representation normalization. Ownership alone never authorizes overwriting a task:
// the complete normalized tree, including unknown fields, must agree.
func TaskDocumentMatches(actual, known []byte, manager string) bool {
	return TaskDocumentMatchesWithResolver(actual, known, manager, ResolveAccountSID)
}

// TaskDocumentMatchesWithResolver makes the OS identity boundary injectable for
// cross-platform tests; production uses ResolveAccountSID. Captured before-state
// account spellings are preserved, not replaced with guessed account names.
func TaskDocumentMatchesWithResolver(actual, known []byte, manager string, resolver AccountSIDResolver) bool {
	if bytes.Equal(actual, known) {
		return true
	}
	sid := taskUser(known)
	generated, err := WindowsTask(manager, sid)
	generatedAfter := err == nil && bytes.Equal(generated, known)
	actualTree, err := taskTree(actual)
	if err != nil {
		return false
	}
	knownTree, err := taskTree(known)
	if err != nil {
		return false
	}
	if generatedAfter && (!normalizeGeneratedTaskUser(actualTree, "Task", sid, resolver) || !normalizeGeneratedTaskUser(knownTree, "Task", sid, resolver)) {
		return false
	}
	if !normalizeTaskTree(actualTree, "Task", generatedAfter) || !normalizeTaskTree(knownTree, "Task", generatedAfter) {
		return false
	}
	a, err := json.Marshal(actualTree)
	if err != nil {
		return false
	}
	b, err := json.Marshal(knownTree)
	return err == nil && bytes.Equal(a, b)
}

type taskXMLNode struct {
	Name       xml.Name
	Attributes []xml.Attr
	Text       string
	Children   []*taskXMLNode
}

func taskTree(raw []byte) (*taskXMLNode, error) {
	normalized, err := normalizeTaskXML(raw)
	if err != nil {
		return nil, err
	}
	decoder := xml.NewDecoder(bytes.NewReader(normalized))
	var root *taskXMLNode
	var stack []*taskXMLNode
	count := 0
	for {
		token, err := decoder.Token()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, closed(diagnostics.Verification, "scheduler_xml")
		}
		switch v := token.(type) {
		case xml.StartElement:
			count++
			if count > 4096 || len(stack) >= 32 {
				return nil, closed(diagnostics.Verification, "scheduler_xml")
			}
			node := &taskXMLNode{Name: v.Name}
			for _, attr := range v.Attr {
				if attr.Name.Local == "xmlns" || attr.Name.Space == "xmlns" {
					continue
				}
				node.Attributes = append(node.Attributes, attr)
			}
			sort.Slice(node.Attributes, func(i, j int) bool {
				a, b := node.Attributes[i].Name, node.Attributes[j].Name
				return a.Space+"/"+a.Local < b.Space+"/"+b.Local
			})
			if len(stack) == 0 {
				root = node
			} else {
				parent := stack[len(stack)-1]
				parent.Children = append(parent.Children, node)
			}
			stack = append(stack, node)
		case xml.EndElement:
			stack = stack[:len(stack)-1]
		case xml.CharData:
			if len(stack) > 0 {
				stack[len(stack)-1].Text += string(v)
			}
		}
	}
	return root, nil
}

// Only defaults documented by the Microsoft Task Scheduler schema may be
// omitted. A changed value, extra action/trigger, unknown node or attribute
// remains in the full tree and causes comparison failure.
var taskSchemaDefaults = map[string]string{
	"Task/Principals/Principal/RunLevel":                      "LeastPrivilege",
	"Task/Settings/AllowStartOnDemand":                        "true",
	"Task/Settings/MultipleInstancesPolicy":                   "IgnoreNew",
	"Task/Settings/DisallowStartIfOnBatteries":                "true",
	"Task/Settings/StopIfGoingOnBatteries":                    "true",
	"Task/Settings/AllowHardTerminate":                        "true",
	"Task/Settings/StartWhenAvailable":                        "false",
	"Task/Settings/RunOnlyIfNetworkAvailable":                 "false",
	"Task/Settings/WakeToRun":                                 "false",
	"Task/Settings/Enabled":                                   "true",
	"Task/Settings/Hidden":                                    "false",
	"Task/Settings/DeleteExpiredTaskAfter":                    "PT0S",
	"Task/Settings/ExecutionTimeLimit":                        "PT72H",
	"Task/Settings/Priority":                                  "7",
	"Task/Settings/RunOnlyIfIdle":                             "false",
	"Task/Settings/DisallowStartOnRemoteAppSession":           "false",
	"Task/Settings/IdleSettings/Duration":                     "PT10M",
	"Task/Settings/IdleSettings/WaitTimeout":                  "PT1H",
	"Task/Settings/IdleSettings/StopOnIdleEnd":                "true",
	"Task/Settings/IdleSettings/RestartOnIdle":                "false",
	"Task/Triggers/LogonTrigger/Enabled":                      "true",
	"Task/Triggers/LogonTrigger/ExecutionTimeLimit":           "PT72H",
	"Task/Triggers/LogonTrigger/Repetition/StopAtDurationEnd": "false",
}

func normalizeTaskTree(node *taskXMLNode, path string, generatedAfter bool) bool {
	if node == nil || node.Name.Space != "http://schemas.microsoft.com/windows/2004/02/mit/task" {
		return false
	}
	if len(node.Children) == 0 {
		node.Text = taskDurationValue(path, node.Text)
	}
	if len(node.Children) > 0 {
		if len(strings.TrimSpace(node.Text)) != 0 {
			return false
		}
		node.Text = ""
		kept := node.Children[:0]
		for _, child := range node.Children {
			childPath := path + "/" + child.Name.Local
			if !normalizeTaskTree(child, childPath, generatedAfter) {
				return false
			}
			if generatedAfter && len(child.Children) == 0 && len(child.Attributes) == 0 {
				if want, ok := taskSchemaDefaults[childPath]; ok && child.Text == want {
					continue
				}
				if childPath == "Task/RegistrationInfo/URI" && child.Text == "\\"+TaskName {
					continue
				}
				if childPath == "Task/Settings/IdleSettings" && child.Text == "" {
					continue
				}
			}
			kept = append(kept, child)
		}
		node.Children = kept
		sort.Slice(node.Children, func(i, j int) bool {
			a, _ := json.Marshal(node.Children[i])
			b, _ := json.Marshal(node.Children[j])
			return bytes.Compare(a, b) < 0
		})
	}
	return true
}

// XML Schema duration uses day/hour/minute/second value units. These narrow
// aliases cover only the fixed scheduler policy and documented default values;
// unknown durations, calendar months/years and changed values remain untouched.
// https://www.w3.org/TR/xmlschema-2/#duration
func taskDurationValue(path, value string) string {
	switch path {
	case "Task/Triggers/LogonTrigger/Repetition/Interval":
		switch value {
		case "P1D", "PT1440M", "PT86400S":
			return "PT24H"
		}
	case "Task/Triggers/LogonTrigger/Delay":
		if value == "PT300S" {
			return "PT5M"
		}
	case "Task/Settings/ExecutionTimeLimit", "Task/Settings/IdleSettings/Duration":
		switch value {
		case "PT600S":
			return "PT10M"
		case "P3D", "PT4320M", "PT259200S":
			return "PT72H"
		}
	case "Task/Settings/IdleSettings/WaitTimeout":
		switch value {
		case "PT60M", "PT3600S":
			return "PT1H"
		}
	case "Task/Triggers/LogonTrigger/ExecutionTimeLimit":
		switch value {
		case "P3D", "PT4320M", "PT259200S":
			return "PT72H"
		}
	case "Task/Settings/DeleteExpiredTaskAfter":
		switch value {
		case "P0D", "PT0M", "PT0H":
			return "PT0S"
		}
	}
	return value
}

// AccountSIDResolver is the OS account identity boundary. It never strips a
// domain or equates display names; the returned SID must match exactly.
type AccountSIDResolver func(identity string) (string, error)

func ResolveAccountSID(identity string) (string, error) {
	if identity == "" || len(identity) > 256 || strings.ContainsAny(identity, "\x00\r\n") {
		return "", closed(diagnostics.Verification, "scheduler_identity")
	}
	if windowsSID(identity) {
		return identity, nil
	}
	if strings.HasPrefix(identity, "S-") {
		return "", closed(diagnostics.Verification, "scheduler_identity")
	}
	account, err := user.Lookup(identity)
	if err != nil || !windowsSID(account.Uid) {
		return "", closed(diagnostics.Verification, "scheduler_identity")
	}
	return account.Uid, nil
}

func TaskUserIdentityMatches(identity, expectedSID string) bool {
	return TaskUserIdentityMatchesWithResolver(identity, expectedSID, ResolveAccountSID)
}
func TaskUserIdentityMatchesWithResolver(identity, expectedSID string, resolver AccountSIDResolver) bool {
	if !windowsSID(expectedSID) || identity == "" || len(identity) > 256 || strings.ContainsAny(identity, "\x00\r\n") {
		return false
	}
	if identity == expectedSID {
		return true
	}
	if windowsSID(identity) || strings.HasPrefix(identity, "S-") || resolver == nil {
		return false
	}
	resolved, err := resolver(identity)
	return err == nil && resolved == expectedSID
}
func windowsSID(s string) bool {
	if len(s) > 184 || !strings.HasPrefix(s, "S-1-") {
		return false
	}
	parts := strings.Split(s, "-")
	if len(parts) < 4 {
		return false
	}
	for _, part := range parts[2:] {
		if part == "" {
			return false
		}
		for _, c := range part {
			if c < '0' || c > '9' {
				return false
			}
		}
	}
	return true
}
func normalizeGeneratedTaskUser(node *taskXMLNode, path, sid string, resolver AccountSIDResolver) bool {
	if path == "Task/Triggers/LogonTrigger/UserId" {
		if len(node.Children) != 0 || !TaskUserIdentityMatchesWithResolver(node.Text, sid, resolver) {
			return false
		}
		node.Text = sid
	}
	for _, child := range node.Children {
		if !normalizeGeneratedTaskUser(child, path+"/"+child.Name.Local, sid, resolver) {
			return false
		}
	}
	return true
}
