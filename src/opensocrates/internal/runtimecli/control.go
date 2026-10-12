package runtimecli

import (
	"fmt"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/application"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/domain"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/persistence"
	"github.com/ParkerHwang/OpenSocrates/src/opensocrates/internal/version"
	"io"
)

// RunControl accepts only the released Codex command forms. Neither artifact
// confirmation nor direct-user authority can be claimed by model CLI flags.
func RunControl(args []string, in io.Reader, out, stderr io.Writer) int {
	valid := len(args) == 3 && args[0] == "apply" && args[1] == "--host" && args[2] == "codex" || len(args) == 1 && args[0] == "codex" || len(args) == 2 && args[0] == "--host" && args[1] == "codex"
	if !valid {
		fmt.Fprintln(stderr, "invalid control arguments")
		return 2
	}
	raw, e := io.ReadAll(io.LimitReader(in, domain.MaxControlBytes+1))
	if e != nil {
		r := domain.NewControlResult("")
		r.ErrorCode = domain.Pointer("internal_error")
		emit(out, r)
		return 0
	}
	root := persistence.Root()
	turns, e := persistence.ExistingTurnStore(root)
	if e != nil {
		r := domain.NewControlResult("")
		r.ErrorCode = domain.Pointer("store_unavailable")
		r.ReasonCode = domain.Pointer("store_unavailable")
		emit(out, r)
		return 0
	}
	app := application.ControlApplication{Turns: turns, Records: persistence.RecordStore{Root: root}, Settings: persistence.SettingsStore{Root: root}, AdapterVersion: version.ProductVersion}
	result := app.Apply(application.ControlRequest{Raw: raw})
	emit(out, result)
	return 0
}
