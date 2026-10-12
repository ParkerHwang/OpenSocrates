package devtools

import (
	"bytes"
	"debug/buildinfo"
	"encoding/json"
	"path/filepath"
	"time"

	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/platform"
)

// Execution architecture is evidence: an emulated x64 executable never yields
// an ARM64 receipt merely because its operating system is Windows ARM64.
func acceptanceExecutableMatchesTarget(path, target string) bool {
	raw, err := readAcceptanceSource(path, 128<<20)
	if err != nil {
		return false
	}
	info, err := buildinfo.Read(bytes.NewReader(raw))
	if err != nil {
		return false
	}
	settings := map[string]string{}
	for _, setting := range info.Settings {
		settings[setting.Key] = setting.Value
	}
	return nativeAcceptanceTargetFor(settings["GOOS"], settings["GOARCH"]) == target && target != "unsupported"
}

// This invokes the actual packaged Go replacement worker with synthetic owned
// local requests. It does not claim signed network delivery or modify an active
// installation; source artifacts are copied into disposable per-user roots.
func acceptanceWindowsNativeHelper(parent, packageRoot, fixture, target string, cases map[string]any) bool {
	if !windowsAcceptanceTarget(target) {
		return false
	}
	helperSource := filepath.Join(packageRoot, "bin", "opensocrates-update-helper.exe")
	managerSource := filepath.Join(packageRoot, "bin", "opensocrates.exe")
	if !acceptanceExecutableMatchesTarget(helperSource, target) || !acceptanceExecutableMatchesTarget(managerSource, target) {
		cases["native_helper_artifact_architecture"] = map[string]any{"pass": false}
		return false
	}
	cases["native_helper_artifact_architecture"] = map[string]any{"pass": true}
	allPass := true
	for _, kind := range []string{"manager", "helper"} {
		root := filepath.Join(parent, "native-helper-"+kind)
		if platform.Mkdir(root) != nil {
			return false
		}
		env, work, err := isolatedAcceptanceEnvironment(filepath.Join(root, "fixture"))
		if err != nil {
			return false
		}
		worker := filepath.Join(root, "worker", "opensocrates-update-helper.exe")
		if err = copyAcceptanceTree(helperSource, worker); err != nil {
			return false
		}
		name, source := "opensocrates.exe", managerSource
		if kind == "helper" {
			name, source = "opensocrates-update-helper.exe", helperSource
		}
		installed := filepath.Join(root, name)
		candidate := filepath.Join(root, "versions", "candidate", name)
		if copyAcceptanceTree(fixture, installed) != nil || copyAcceptanceTree(source, candidate) != nil {
			return false
		}
		previous, e1 := platform.SHA256File(installed, 128<<20)
		next, e2 := platform.SHA256File(candidate, 128<<20)
		helperHash, e3 := platform.SHA256File(worker, 128<<20)
		if e1 != nil || e2 != nil || e3 != nil || previous == next {
			return false
		}
		request := platform.ReplacementRequest{Schema: 1, OperationID: "9661c9a0b58687fe5b565db800e91073", Target: installed, Candidate: candidate, Backup: installed + ".previous", PreviousSHA256: previous, CandidateSHA256: next, HelperSHA256: helperHash, TimeoutSeconds: 10}
		requestPath := filepath.Join(root, "replacement.json")
		raw, err := json.Marshal(request)
		if err != nil || platform.ExclusiveWrite(requestPath, append(raw, '\n'), 0600) != nil {
			return false
		}
		invoke := func() bool {
			_, stderr, err := runAcceptanceProcess(worker, []string{"--request", requestPath}, nil, env, work, 20*time.Second)
			return err == nil && len(stderr) == 0
		}
		replaced := invoke() && acceptanceHashMatches(installed, next) && acceptanceHashMatches(request.Backup, previous)
		cases["windows_native_"+kind+"_replacement"] = map[string]any{"pass": replaced}
		allPass = allPass && replaced
		if !replaced {
			continue
		}
		repeated := invoke() && acceptanceHashMatches(installed, next) && acceptanceHashMatches(request.Backup, previous)
		cases["windows_native_"+kind+"_replacement_recovery"] = map[string]any{"pass": repeated}
		allPass = allPass && repeated
		// Model an interruption after moving the original to its verified backup.
		if platform.Remove(installed) != nil {
			return false
		}
		_, _, restoreError := runAcceptanceProcess(worker, []string{"--request", requestPath}, nil, env, work, 20*time.Second)
		journal, readError := platform.ReadFile(requestPath+".journal", 64<<10)
		var state map[string]any
		rolledBack := restoreError != nil && acceptanceHashMatches(installed, previous) && readError == nil && json.Unmarshal(journal, &state) == nil && state["stage"] == "rolled-back"
		cases["windows_native_"+kind+"_verified_rollback"] = map[string]any{"pass": rolledBack}
		allPass = allPass && rolledBack
	}
	return allPass
}

func acceptanceHashMatches(path, expected string) bool {
	actual, err := platform.SHA256File(path, 128<<20)
	return err == nil && actual == expected
}
