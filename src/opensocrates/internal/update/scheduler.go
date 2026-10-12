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
	"strconv"
	"strings"
	"time"
	"unicode/utf16"
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
<Triggers><LogonTrigger><Enabled>true</Enabled><UserId>` + escape(sid) + `</UserId><Delay>PT5M</Delay><Repetition><Interval>PT24H</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition></LogonTrigger></Triggers>
<Principals><Principal id="User"><UserId>` + escape(sid) + `</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable><Enabled>true</Enabled><ExecutionTimeLimit>PT10M</ExecutionTimeLimit></Settings>
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
	b = decodeWindows(b)
	if e != nil {
		return s, e
	} // Unknown access failure is never interpreted as absence.
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
	if actual.Installed == after.Installed && actual.Registered == after.Registered && actual.Data["document"] == after.Data["document"] {
		return nil
	}
	// A journaled command may have stopped the task or replaced its document
	// before interruption. Only either known document (or an absent identity)
	// can participate in recovery; changed foreign documents always conflict.
	if actual.Installed && actual.Data["document"] != before.Data["document"] && actual.Data["document"] != after.Data["document"] {
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
	if e = platform.AtomicWrite(task, doc, 0600); e != nil {
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
	if want.Installed && a.OS == "darwin" && got.Data["document"] != want.Data["document"] {
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
	var t struct {
		Description string `xml:"RegistrationInfo>Description"`
		Actions     []struct {
			Command   string `xml:"Command"`
			Arguments string `xml:"Arguments"`
		} `xml:"Actions>Exec"`
		UserID        string `xml:"Principals>Principal>UserId"`
		TriggerUserID string `xml:"Triggers>LogonTrigger>UserId"`
		LogonType     string `xml:"Principals>Principal>LogonType"`
		RunLevel      string `xml:"Principals>Principal>RunLevel"`
		Delay         string `xml:"Triggers>LogonTrigger>Delay"`
		Interval      string `xml:"Triggers>LogonTrigger>Repetition>Interval"`
		Instances     string `xml:"Settings>MultipleInstancesPolicy"`
	}
	if xml.Unmarshal(b, &t) != nil || len(t.Actions) != 1 || t.Actions[0].Command != manager || t.Actions[0].Arguments != "auto-update run --scheduled" || t.LogonType != "InteractiveToken" || t.RunLevel != "LeastPrivilege" || !strings.Contains(t.Description, "owned by "+Owner) || t.Delay != "PT5M" || t.Interval != "PT24H" || t.Instances != "IgnoreNew" || !strings.HasPrefix(t.UserID, "S-1-") || t.TriggerUserID != t.UserID {
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
		if e.OS != "windows" || e.Arch != "amd64" {
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
